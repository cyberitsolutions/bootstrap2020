#include <stdio.h>
#include <stdlib.h>
#include <sys/mount.h>

/* FIXME: add getopts parsing */
/*
  This whole approach goes into the Too Hard basket for now, I think:

  10:29 <mooff> "let's get rid of coreutils, all you need is a c compiler"
  10:30 <mooff> "shells? completely unnecessary. i just use butterflies"
  11:25 <twb> mooff: OK, you were right.
              It's slightly harder than I thought.

              1. need to parse -o X,Y,Z into
                 "options for nfs driver" (passed as-is) and
                 "options for mount" (passed as an intger, MS_NODEV | MS_NOSUID | ...).

              2. must pass addr=1.2.3.4 even if user doesn't specify it.
                 Meaning if user does "mount.nfs example.com:/x /x",
                 you need to gethostbyname.

              In userspace you can use libmount1 to do some of that, but
              the initrd shouldn't need that.
*/
int main() {
        int ret;
        ret = mount("10.0.2.100:/srv/netboot", "/mnt", "nfs", 0, "vers=4.2,addr=10.0.2.100,clientaddr=10.0.2.15");
        if (ret != 0) {
                fprintf(stderr, "mount(2) failed; see kernel log for details.");
        }
        exit(ret);
}
