#!/usr/bin/python3

# Goal: rewrite logcheck to
#  • use pipelines instead of tempfiles (efficiency)
#  • use journalctl --since, not logtail + logfiles, thus
#    • avoids the need for rsyslog, logrotate, cron
#    • inappropriate for centralized logserv (journald doesn't do RELP)
#
# FIXME: rsnapshot Depends: logrotate, which will keep it and cron installed ☹
# FIXME: requires installing python3, which ends up ADDING 25MiB.
# NOTE: cracking.d and violations.d are NOT SUPPORTED.

import argparse
import collections
import contextlib
import datetime
import fcntl
import os
import re
import subprocess
import tempfile


_TIMESTAMP_PATH = '/var/log/.last-journalcheck'


def main():
    with lock():
        conf = parse_args()
        with tempfile.TemporaryDirectory() as d:
            pattern_paths = normalize_pattern_paths(conf, d)
            pipeline(conf, pattern_paths)
        maybe_save_timestamp(conf)


@contextlib.contextmanager
def lock():
    # This file handle MUST stay open for the entire runtime of this program.
    # It is how we prevent two runs from overlapping.
    with open('/run/lock/journalcheck', 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


# Save our "until" to a file, to be the next run's "since".
def maybe_save_timestamp(conf):
    if conf.save:
        with open(_TIMESTAMP_PATH, 'w') as f:
            print(conf.until, file=f)


# Load last run's "since", to be our "until".
# If "journalctl --save" has neve run before, we check the entire journal!
def maybe_load_timestamp():
    try:
        with open(_TIMESTAMP_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def normalize_pattern_paths(conf, tempdir):
    # grep --file doesn't understand blank lines or comments.
    # We must pre-process the filters to remove these lines.
    pattern_path = os.path.join(tempdir, 'all.grep')
    with open(pattern_path, 'wb') as f:
        subprocess.check_call(['grep', '-vEh', '^[[:space:]]*($|#)',
                               '--'] + conf.pattern_paths,
                              stdout=f)
    # rsyslog and journalctl both default to a STUPID legacy format (Oct 17 01:02:03).
    # They both support a (RFC3339-like) ISO 8601 profile, but THEY ARE DIFFERENT.
    # On datasafe3, we avoid this by leaving everything in the default (stupid) format.
    # Elsewhere, the code below exists to roll back Cyber BCP's change, so that
    # the rules once again match the default stupid format.
    # This is easier than fighting journalctl --output=short-iso. —twb, Oct 2018
    if conf.rfc3339_rules:
        with open(pattern_path, 'rb') as src:
            with open(pattern_path + '~', 'wb') as dst:
                for line in src:
                    dst.write(line.replace(rb'^[0-9T.:+-]{32} ', rb'^... .. ..:..:.. '))
        os.rename(pattern_path + '~', pattern_path)
    # grep -vE is VERY inefficient with ≫1K patterns and ≫1M log lines, so
    # we break it up into a pipeline of greps with fewer patterns in each.
    # This can reduce the runtime from _WEEKS_ to minutes.
    # NOTE: grep --file=x --file=y is no faster than grep --file=x+y.
    # NOTE: put your most common patterns at the TOP of the FIRST filter file.
    #       For example, PrisonPC logs are about 10% popcon lines, so
    #       making that the first pattern REALLY helps.
    subprocess.check_call(['split', pattern_path, pattern_path])
    os.remove(pattern_path)
    pattern_paths = sorted(os.path.join(tempdir, p)
                           for p in os.listdir(tempdir))
    if conf.test:
        assert len(pattern_paths) == 1, 'Too many patterns for --test!'
    return pattern_paths


def pipeline(conf, pattern_paths):
    procs = []              # accumulator
    procs.append(
        subprocess.Popen(
            ['journalctl', '--system', '--merge',
             '--until', conf.until,
             *(['--since', conf.since] if conf.since else []),
             *conf.extra_journalctl_args],
            stdout=subprocess.PIPE))
    for path in pattern_paths:
        procs.append(
            subprocess.Popen(
                ['grep',
                 '-vE' if conf.test is False else '-E',
                 '--file', path],
                stdin=procs[-1].stdout,
                stdout=subprocess.PIPE,
                # UTF-8 decoding is slow (about 30% of total runtime), so
                # tell grep to operate on bytes (not unicode strings).
                env={'LC_COLLATE': 'C'}))

    # FIXME: using a tempfile for this is UGLY.
    with tempfile.TemporaryFile() as summarize_buffer:
        if conf.summarize:
            # Using sed because 1) faster than python; and 2) the patterns
            # are routinely site-specific, so they might as well be in a
            # discrete file.
            procs.append(
                subprocess.Popen(
                    ['sed', '-rf', '/etc/journalcheck-summarize.sed'],
                    stdin=procs[-1].stdout,
                    stdout=subprocess.PIPE,
                    env={'LC_COLLATE': 'C'}))

            # Automatically collate all the lines from sed!
            # NOTE: unlike syslog-summary, this does not preserve input order.
            summary = collections.Counter(procs[-1].stdout)
            summarize_buffer.writelines(
                '{:8} '.format(v).encode() + k
                for k, v in sorted(summary.items()))
            summarize_buffer.flush()
            summarize_buffer.seek(0)           # rewind to the start for mail/cat to read from

        # quick-and-dirty send-an-email
        # NOTE: this MUST run BEFORE we check the exit statuses, or
        #       we deadlock waiting for procs with full output buffers!
        # FIXME: when ALL output is filtered, this still sends an email.
        #        In practice currently there is ALWAYS at least this line:
        #          -- Logs begin at …, end at …. --
        subprocess.check_call(
            (['mail',
              '-s', 'logcheck {} {}'.format(os.uname().nodename, conf.until),
              '--'] + conf.email_recipients)
            if conf.email_recipients else
            ['cat'],
            stdin=summarize_buffer if conf.summarize else procs[-1].stdout)

    # Check that ALL processes exited successfully.
    # For journalctl only exit(0) is "success".
    # For grep, exit(1) is also "success" - no matches, but also no errors.
    assert procs[0].wait() == 0  # journalctl proc
    for proc in procs[1:]:
        assert proc.wait() in (0, 1)  # matches (0) or no matches (1)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Like logcheck(8), but read log events from the systemd journal (not syslog).'
        ' CRON EXAMPLE: @hourly root journalctl --save --to admin@example.com')
    parser.add_argument('--file',
                        dest='pattern_paths',
                        metavar='PATH',
                        nargs='+',
                        default=sorted((os.path.join(d, p)
                                        for d in ('/etc/logcheck/ignore.d.workstation/',
                                                  '/etc/logcheck/ignore.d.server/',
                                                  '/etc/logcheck/ignore.d.paranoid/')
                                        for p in os.listdir(d)
                                        # Copied from run-parts(8) manpage.
                                        if not p.endswith('.dpkg-old')
                                        if not p.endswith('.dpkg-dist')
                                        if not p.endswith('.dpkg-new')
                                        if (re.fullmatch(r'(^[a-z0-9]+$)', p) or  # noqa: W504
                                            re.fullmatch(r'(^_?([a-z0-9_.]+-)+[a-z0-9]+$)', p) or  # noqa: W504
                                            re.fullmatch(r'(^[a-zA-Z0-9_-]+$)', p))),
                                       # Move local-X files to the front of the list,
                                       # because they are probably the bulk of the messages, and
                                       # we want to ignore them in the first log.
                                       key=lambda x: not os.path.basename(x).startswith('local')),
                        help='A list of files to be fed to grep -vE --file=X.')
    parser.add_argument('--to',
                        dest='email_recipients',
                        metavar='ADDR',
                        nargs='+',
                        default=None,
                        help='If used, output is emailed to these recipients.')
    parser.add_argument('--since', metavar='DATETIME', default=maybe_load_timestamp())
    parser.add_argument('--until', metavar='DATETIME', default=str(datetime.datetime.now()))
    parser.add_argument('--summarize', action='store_true',
                        help='group messages and show counts (not timestamps)')
    g = parser.add_mutually_exclusive_group()
    g.add_argument('--save', action='store_true',
                   help='Record the current time; the next logcheck will only check newer log events.')
    g.add_argument('--test', action='store_true',
                   help='Run grep -E (not grep -vE) — useful for testing new filters.')
    parser.add_argument('extra_journalctl_args', nargs='*',
                        help='This lets you specify things like -p4 or --unit=slapd')
    g = parser.add_mutually_exclusive_group()
    g.add_argument('--rfc3339-rules',
                   action='store_true',
                   default=os.path.exists('/etc/rsyslog.conf'),
                   help='Expect logcheck rules to whitelist RFC3339 timestamps,'
                   ' not legacy MMM DD HH:MM:SS timestamps'
                   ' (on by default if rsyslog is installed)')
    g.add_argument('--legacy-rules',
                   dest='rfc3339_rules',
                   action='store_false')
    conf = parser.parse_args()
    return conf


if __name__ == '__main__':
    main()
