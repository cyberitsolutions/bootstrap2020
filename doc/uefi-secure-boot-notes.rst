https://www.rodsbooks.com/efi-bootloaders/

https://blog.hansenpartnership.com/the-meaning-of-all-the-uefi-keys/ says:

    * the key chain is only verified back to the key in the databases and no further.
    * none of the keys has to be self signed
    * the usual TLS approach to verify all the way to the root CA is *NOT* done.

    * if you know the PK keypair you own the platform.
    * the PK keypair is *NOT* enough, because
    * to change the platform you have to be able to execute binaries, and
    * the platform will only execute binaries signed by a key either in KEK or db (not signed by PK directly).
    * to take control of your platform by installing a platform key, you *MUST* also add the PK (or another keypair you control) to the KEK or db, so you can sign binaries with it and have them execute.

https://uefi.org/sites/default/files/resources/Improving%20Platform%20Security%20with%20UEFI%20Secure%20Boot%20and%20UEFI%20Variables_20160318.pdf#page=11 →
https://old.reddit.com/r/sysadmin/comments/s0o4vs/uefi_audit_and_deployed_mode/ says:

    `Deployed mode` is basically a more strict version of the normal Secure Boot mode (i.e. `User Mode`).
    It does all the same things that User Mode does, except it also
    blocks certain programmatic methods that could be used to alter
    the Secure Boot mode without a user physically booting into UEFI
    settings and changing it there.

https://www.platformsecuritysummit.com/2018/speaker/kiper/PSEC2018-UEFI-Secure-Boot-shim-Xen-Daniel-Kiper.pdf#page=12 says:

    The signature database variables db, dbt, dbx, and dbr must be
    stored in tamper-resistant non-volatile storage. (UEFI 2.7 spec)

:Q: how do I even look at the dbt and dbr?  Does OVMF implement them?  What version of UEFI specification does OVMF implement?  dbt only arrived in UEFI 2.5 IIUC...

:A: ``bootctl`` claims ``Firmware: UEFI 2.70 (EDK II 1.00)``... does that mean it conforms to UEFI standard version 2.70?  Or does that mean that it's EDK2 version 2.70?  ``dpkg-query –show ovmf`` says ``ovmf	2022.11-6+deb12u1``...

In #debian-rant:

| 05:47 <twb> Can mokutil edit PK/KEK/DB/DBX *at all*?  It seems like it can only view it, and editing it must be done with some other tool, and MOK can only actually edit the lists used by shim (not by the UEFI firmware itself)
| 05:48 <twb> I guess that makes sense because "MOK" *is* the shim-only thing
| 06:13 <REDACTED> exactly
| 06:14 <REDACTED> you can't modify these variables using boot services, not runtime service
| 06:15 <REDACTED> sorry
| 06:15 <REDACTED> s/can't/can only/
| 06:15 <twb> I'm struggling to find *any*  way to edit it short of booting the system and then doing it via the UEFI config menus
| 06:15 <REDACTED> that's how it's normally done
| 06:15 <twb> My main issue with that is it can't be scripted
| 06:16 <REDACTED> control over those databases is only done via firmware stuff
| 06:16 <twb> Unless I understand all this redfish protocol stuff
| 06:16 <twb> Since I'm working on VMs what I really want is just a tool that creates/views/edits OVMF_CODE_4M.fd directly from the host system
| 06:17 <twb> But it seems like nobody else has even asked for this before, let alone built it
| 06:17 <REDACTED> oh, that's doable totally
| 06:17 <REDACTED> sec...
| 06:17 <twb> I found one Intel python library that does it whose github repo is secret
| 06:17 <twb> But it looked kinda awful
| 06:18 <REDACTED> see the python3-virt-firmware package
| 06:18 <twb> I haven't yet found what part of the edk2 git repo creates the regular OVMF_CODE_4M.snakeoil.fd and OVMF_CODE_4M>ms.fd
| 06:18 <twb> ah thanks let me look at that...
| 06:18 <REDACTED> I use that all the time in local CI for shim
| 06:18 <twb> OK that looks like exactly what I want
| 06:18 <REDACTED> you know, asking questions in a useful channel might get you further in future
| 06:19 <REDACTED> you're just luck I happened to be here
| 06:19 <twb> I asked in #edk2 and I was in #qemu last week
| 06:19 <REDACTED> #debian-efi ...
| 06:19 <twb> Oh, OK.  It didn't seem like it was really a Debian thing
