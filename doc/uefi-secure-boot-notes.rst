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



In #debian-boot and #debian-efi:

| 17:26 <twb> Does https://deb.debian.org/debian/dists/stable/main/installer-amd64/current/images/netboot/mini.iso have the relevant signatures so it'll boot on a system with Secure Boot enabled and https://www.microsoft.com/pkiops/certs/MicCorUEFCA2011_2011-06-27.crt in the trusted keyring?
| 17:26 <twb> And if not, what's the smallest image that does have that set up
| 17:34 <REDACTED> it should. why?
| 17:35 <twb> I'm messing with secure boot in qemu and I saw failures that *maybe* were that problem, but I guess were actually me screwing up somewhere else
| 17:41 <REDACTED> hmm, you are correct, this thing does not secure boot. hmpf
| 17:41 <twb> oh phew I feel better now, knowing it's not my fault
| 17:42 <twb> I definitely don't trust my understanding enough of secure boot to storm in here and go "it's broken, fix it!"
| 17:45 <REDACTED> so the smallest secure boot capable boot thing is https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.1.0-amd64-netinst.iso
| 17:45 <twb> Thanks for confirming, I was afraid of that
| 17:45 <REDACTED> and yes, this boot chain is still signed with the 2011 uefi root
| 17:50 <twb> BTW it would be nice if there was a signed UKI next to mini.iso (ukify build --output=minix64.efi  --secureboot-private-key=key.pem --secureboot-certificate=cert.pem --linux=debian-installer/amd64/linux --initrd=debian-installer/amd64/initrd.gz)
| 17:50 <twb> cos then I could just drop that into any old ESP:\
| 17:48 <REDACTED> wow. "signed by DO NOT TRUST - AMI Test PK"
| 17:52 <twb> oh I guess I should have asked here instead of -boot?
| 17:53 <twb> Sorry -- end of work day for me and I'll already feeling a bit flaky today
| 17:59 <twb> if I want mini.iso to be signed by a MS key most devices trust by default, what pseudo-package do I reportbug against?

::

    18:32 <f_g> https://paste.debian.net/1400012/
    18:33 <f_g> it then proceeds with https://paste.debian.net/1400014/ so maybe there is something else in there that is signed by some weird key?
    18:34 <twb> How do you get it to emit that debugging log?  My notes from 2024 suggested -debugcon mon:stdio -global isa-debugcon.iobase=0x402 but I couldn't get that to work today. (https://github.com/tianocore/edk2/blob/master/OvmfPkg/README#L88)
    18:40 <f_g> serial console
    18:53 <twb> Hrm, on serial console all I see is BdsDxe: loading Boot0001 "UEFI Misc Device" from PciRoot(0x0)/Pci(0x1,0x0) BdsDxe: starting Boot0001 "UEFI Misc Device" from PciRoot(0x0)/Pci(0x1,0x0)
    18:54 <twb> With both legacy /usr/share/ovmf/OVMF.fd and also with /usr/share/OVMF/OVMF_CODE_4M.secboot.fd + writable copy of OVMF_VARS_4M.fd and also driver=cfi.pflash01,property=secure,value=on
    18:58 <f_g> you need to set an efi var as well (SHIM_VERBOSE)
    18:58 <twb> Ah per my link, writing to the serial console was the old default
    19:13 <twb> f_g: how do you set an EFI variable from outside the VM?  I tried -device uefi-vars-x64,force-secure-boot=on,disable-custom-mode=on,jsonfile=./uefi-vars.json with {"SHIM_VERBOSE": "65535"}, but that failed with "Parameter 'version' is missing"
    19:13 <f_g> I set it from inside :-P
    19:14 <twb> And I can't understand what foramt virt-fw-vars wants for --set-json, it seems to want {"SHIM_VERBOSE:" {"attr": <something>}}
    19:14 <twb> hmph OK
    19:17 <twb> OK FTR I think qemu's uefi-vars-x64 driver wants the same format as virt-fw-json --json-output emits, which is somethign like {"version": 2, "variables": [{<some attr and GUID nonsense>}]}
    19:17 <twb> I haven't got an example variable yet so I dunno what e.g. mokutil would write in there.  Presumably there are "well known" GUIDs rather than named variables
    19:22 <f_g> SHIM_VERBOSE-605dab50-e046-4300-abb6-3dd810dd8b23 . you can set it using mokutil
