#!/usr/bin/python3
# https://sources.debian.org/src/ghostscript/9.56.1~dfsg-1/demos/python/gsapi.py/
# FIXME: license
# FIXME: description

import argparse
import ctypes
import ctypes.util
import pathlib
import subprocess

import gi
gi.require_version('Notify', '0.7')
import gi.repository.Notify     # noqa: E402


class GSError(RuntimeError):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--DPI', type=int, default=96)
    parser.add_argument('input_path', type=pathlib.Path)
    args = parser.parse_args()
    args.output_path = args.input_path.with_suffix(f'.{args.DPI} DPI.pdf')
    args.gs_command = (
        'gs',
        # These options are taken from /bin/ps2pdfwr
        '-P-',
        '-dSAFER',
        '-q',
        '-P-',
        '-dNOPAUSE',
        '-dBATCH',
        '-sDEVICE=pdfwrite',
        '-sstdout=%stderr',
        f'-sOutputFile={args.output_path}',
        # Everything else is made-up.
        '-dPDFSETTINGS=/screen',  # low-quality settings
        '-dCompatibilityLevel=1.7',  # ...except not PDF 1.5
        f'-dColorImageResolution={args.DPI}',
        f'-dGrayImageResolution={args.DPI}',
        f'-dMonoImageResolution={args.DPI}',)

    gi.repository.Notify.init('PDF compressor')
    try:
        ghostscript(args)
        input_size = args.input_path.stat().st_size
        output_size = args.output_path.stat().st_size
        size_difference = output_size / input_size
    except GSError:
        gi.repository.Notify.Notification.new(
            summary='Compression failed (internal error)',
            body=f'Failed to compress PDF {args.input_path.name}',
            icon='dialog-error-symbolic').show()
        exit(1)
    if size_difference > 0.9:
        gi.repository.Notify.Notification.new(
            summary='Compression failed (not smaller)',
            body=f'Cannot make {args.input_path.name} significantly smaller',
            icon='dialog-error-symbolic').show()
        args.output_path.unlink()  # so delete it
    else:
        gi.repository.Notify.Notification.new(
            summary=f'Compression succeeded ({1 - size_difference:.0%} smaller)',
            body=f'Opening {args.output_path.name} now…',
            icon='dialog-information-symbolic').show()
        subprocess.check_call(['exo-open', args.output_path])


def ghostscript(args):
    def check(returncode):
        if returncode < 0:
            raise RuntimeError('GSError', returncode)

    library_name = ctypes.util.find_library('gs')
    if not library_name:
        raise RuntimeError('libgs.so not installed?')
    libgs = ctypes.CDLL(library_name)
    instance = ctypes.c_void_p()
    check(libgs.gsapi_new_instance(
        ctypes.byref(instance),
        ctypes.c_void_p(0)))
    check(libgs.gsapi_set_arg_encoding(instance, 1))  # 1 = UTF-8

    # Create copy of args in format expected by C.
    argc = len(args.gs_command)
    argv = (ctypes.POINTER(ctypes.c_char) * (argc + 1))()
    for i, arg in enumerate(args.gs_command):
        argv[i] = ctypes.create_string_buffer(arg.encode('UTF-8'))
    argv[argc] = None
    check(libgs.gsapi_init_with_args(instance, argc, argv))

    pexit_code = ctypes.c_int()
    input_path_encoded = str(args.input_path).encode('UTF-8')
    check(libgs.gsapi_run_file(instance, input_path_encoded, None, ctypes.byref(pexit_code)))
    check(libgs.gsapi_exit(instance))
    check(libgs.gsapi_delete_instance(instance))
    check(pexit_code.value)


if __name__ == '__main__':
    main()
