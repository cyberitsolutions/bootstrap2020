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
