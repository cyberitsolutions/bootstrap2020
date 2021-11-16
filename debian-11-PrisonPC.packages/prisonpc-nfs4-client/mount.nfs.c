#include <stdio.h>
#include <stdlib.h>
#include <sys/mount.h>

/* FIXME: add getopts parsing */
int main() {
        int ret;
        ret = mount("10.0.2.100:/srv/netboot", "/mnt", "nfs", 0, "vers=4.2,addr=10.0.2.100,clientaddr=10.0.2.15");
        if (ret != 0) {
                fprintf(stderr, "mount(2) failed; see kernel log for details.");
        }
        exit(ret);
}
