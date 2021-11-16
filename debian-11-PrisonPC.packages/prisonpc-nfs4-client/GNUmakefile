all: mount.nfs nfsmount
clean:
	rm -f *.o mount.nfs nfsmount
install:
	install -d        $(DESTDIR)/sbin
	install mount.nfs $(DESTDIR)/sbin
	install -d        $(DESTDIR)/usr
	install -d        $(DESTDIR)/usr/lib
	install -d        $(DESTDIR)/usr/lib/klibc
	install -d        $(DESTDIR)/usr/lib/klibc/bin
	install nfsmount  $(DESTDIR)/usr/lib/klibc/bin/nfsmount-prisonpc
nfsmount: CC=klcc
