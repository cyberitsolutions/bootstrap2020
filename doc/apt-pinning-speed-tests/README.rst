Analysis
========

As at apt 3.0.3 (using Debian 13's package lists)...

* "apt show mg" is slower with pins, but
  "apt-cache show mg" is not.

:**CONCLUSION**:
   new CLI is loading pins even when it does not need to?

* One glob matching one package costs 0.5 seconds.
* One glob matching 12000 packages costs 0.8 seconds.
* 13 globs matching 15000 packages costs 2.9 seconds.
* 13 globs matching     0 packages costs 2.8 seconds.
* 61 globs matching 16000 packages costs 9.2 seconds.
* 2 regexps matching 17000 packages costs 91.4 seconds.
* one glob per stanza (all same priority) is slightly faster?!
* one glob per stanza (diferent priorities) is slightly slower.
* foo vs src:foo is has no impact.
* using very negative priorities has no impact.
* using a broad range of negative priorities has no impact.

:**CONCLUSION**:
   apt_preferences(5) scales poorly with the number of patterns.
   The number of matches, stanzas, &c has much less impact.
   Using regexps instead of globs is even worse.

As at apt 3.2.0 (using Debian 13's package lists)...

The timings roughly match, i.e. not magically better.

------------------------------------------------------------

PS: I acknowledge the patterns in my tests indicate I'm doing weird/dumb things.
But I think there are probably legitimate reasons to have 10 globs?
Or... thinking about it more, I guess most use cases are either
"Package: *" (testing/unstable hybrids) or
"Package: foo" (apt-listbugs pinning a specific known-buggy package).
And neither of those are globs...  OK, yes,
pinning "Package: *" takes ~0.5s and
pinning "Package: * * *" takes ~2s and
pinning 62 specific packages (src:libreoffice, src:linux, clang-17, clang-18, &c) takes 0.4s.
pinning 13000 specific packages (each foo-dev by name) takes 0.4s.
So this slowdown hits ONLY when you have globs rather than exact package names.
Which is a MUCH less common thing to do.

Here's an simpler comparison showing the symptoms are definitely only
with glob/regex patterns, not literals.

| root@hera:/# printf >/etc/apt/preferences  'Pin-Priority: -1\nPin: version *\nPackage: %s\n' '*-dev *-devel *-dbg *-dbgsym *-prof *-src *-source *-dkms *-debug *-compiler *-server *-test *-tests'; time apt-cache policy | wc -l
| 14747
| real    **0m2.039s**
| user    0m1.962s
| sys     0m0.087s
|
| root@hera:/# printf >/etc/apt/preferences  'Pin-Priority: -1\nPin: version *\nPackage: %s\n' '/-(dev|devel|dbg|dbgsym|prof|src|source|dkms|debug|compiler|server|test|tests)$/'; time apt-cache policy | wc -l
| 14747
| real    **0m6.787s**
| user    0m6.764s
| sys     0m0.026s
|
| root@hera:/# printf >/etc/apt/preferences  'Pin-Priority: -1\nPin: version *\nPackage: %s\n' "$(apt-cache pkgnames | grep -E -e "-(dev|devel|dbg|dbgsym|prof|src|source|dkms|debug|compiler|server|test|tests)$" | tr '\n' ' ')"; time apt-cache policy | wc -l
| 14747
| real    **0m0.176s**
| user    0m0.140s
| sys     0m0.043s
