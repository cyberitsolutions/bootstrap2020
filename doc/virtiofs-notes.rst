Here's how I did this shit last time::

    cmd=(
        sudo mmdebstrap bookworm /var/lib/libvirt/images/tiger/rootfs
        --aptopt='Acquire::http::Proxy "http://apt-cacher-ng.cyber.com.au:3142"'
        --aptopt='Acquire::https::Proxy "DIRECT"'
        --variant=apt
        # Booting
        --include='linux-image-cloud-amd64 initramfs-tools init dbus-broker'
        --essential-hook='mkdir -p $1/etc/initramfs-tools'
        --essential-hook='echo virtiofs >$1/etc/initramfs-tools/modules'
        # Networking
        --include='netbase libnss-resolve libnss-myhostname systemd-timesyncd'
        --customize-hook='chroot $1 cp -alf /lib/systemd/resolv.conf /etc/resolv.conf'
        --customize-hook='printf "%s\n" >$1/etc/systemd/network/upstream.network "[Match]" "Name=en*" "[Network]" "DHCP=yes" "[DHCPv4]" "UseDomains=yes"'
        --customize-hook='chroot $1 systemctl enable systemd-networkd systemd-timesyncd'
        # Sigh, do I really need this still?
        --essential-hook='echo tiger >$1/etc/hostname'
        # Remote access
        --include='tinysshd rsync'
        --essential-hook='install -dm700 $1/root/.ssh'
        --essential-hook='wget -qO- https://github.com/trentbuck.keys https://github.com/mijofa.keys https://github.com/emja.keys >$1/root/.ssh/authorized_keys'
        # Local serial console access
        --essential-hook='chroot $1 passwd --delete root'
        # apt/dpkg sync thrash on virtiofs on zfs is too slow, ENABLE DATA LOSS
        --include=eatmydata
        --customize-hook='ln -s /usr/bin/eatmydata $1/usr/local/bin/dpkg'
        # FUCK YOU ansible, make ansible work without needing an inventory.yaml to override ansible's defaults.
        --include=openssh-sftp-server,python3,ca-certificates
        --customize-hooks='echo TINYSSHDOPTS=-vxsftp=/usr/lib/sftp-server >$1/etc/default/tinysshd'
    )
    "${cmd[@]}"

.. NOTE:: you need to add the ``xmlns=`` at the top, or the ``qemu:`` at the bottom will be silently deleted!

And here's the domain.xml::

    <!-- CHANGED: xmlns:qemu= -->
    <domain type='kvm' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
      <!-- CHANGED: firmware= -->
      <os firmware='efi'>
        <type arch='x86_64' machine='pc-q35-8.2'>hvm</type>
        <!-- CHANGED: added direct boot args -->
        <kernel>/var/lib/libvirt/images/tiger/rootfs/vmlinuz</kernel>
        <initrd>/var/lib/libvirt/images/tiger/rootfs/initrd.img</initrd>
        <cmdline>rootfstype=virtiofs root=tiger rw console=ttyS0 loglevel=2</cmdline>
        <boot dev='hd'/>
      </os>
      <!-- CHANGED: remove original bridge neworking and add slirp w/ port forward. -->
      <!-- The ONLY reason I do this is so even before the VM has a firewall, all its inbound ports are blocked except 22. -->
      <qemu:commandline>
        <qemu:arg value='--device'/>
        <qemu:arg value='driver=pcie-root-port,id=BecauseVirtdCannotDoHostFwd0,bus=pcie.0,addr=0xf'/>
        <qemu:arg value='--device'/>
        <qemu:arg value='driver=virtio-net-pci,netdev=BecauseVirtdCannotDoHostFwd2,id=BecauseVirtdCannotDoHostFwd1,mac=52:54:00:85:3d:a8,bus=BecauseVirtdCannotDoHostFwd0,addr=0x0'/>
        <qemu:arg value='--netdev'/>
        <qemu:arg value='type=user,id=BecauseVirtdCannotDoHostFwd2,hostfwd=tcp::2023-:22,net=192.168.87.0/24,hostname=tiger.cyber.com.au,dnssearch=cyber.com.au'/>
      </qemu:commandline>
      <name>tiger</name>
      <uuid>1c69145c-e229-4ee3-8985-ef907493bb38</uuid>
      <metadata>
        <libosinfo:libosinfo xmlns:libosinfo="http://libosinfo.org/xmlns/libvirt/domain/1.0">
          <libosinfo:os id="http://debian.org/debian/12"/>
        </libosinfo:libosinfo>
      </metadata>
      <memory unit='KiB'>2097152</memory>
      <currentMemory unit='KiB'>2097152</currentMemory>
      <memoryBacking>
        <source type='memfd'/>
        <access mode='shared'/>
      </memoryBacking>
      <vcpu placement='static'>2</vcpu>
      <features>
        <acpi/>
        <apic/>
        <vmport state='off'/>
      </features>
      <cpu mode='host-passthrough' check='none' migratable='on'/>
      <clock offset='utc'>
        <timer name='rtc' tickpolicy='catchup'/>
        <timer name='pit' tickpolicy='delay'/>
        <timer name='hpet' present='no'/>
      </clock>
      <on_poweroff>destroy</on_poweroff>
      <on_reboot>restart</on_reboot>
      <on_crash>destroy</on_crash>
      <pm>
        <suspend-to-mem enabled='no'/>
        <suspend-to-disk enabled='no'/>
      </pm>
      <devices>
        <!-- CHANGED: added rootfs -->
        <filesystem type='mount' accessmode='passthrough'>
          <driver type='virtiofs'/>
          <binary path='/usr/libexec/virtiofsd'/>
          <source dir='/var/lib/libvirt/images/tiger/rootfs'/>
          <target dir='tiger'/>
          <address type='pci' domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
        </filesystem>
        <!-- CHANGED: remove spice, video, tablet, &c bullshit, added serial console -->
        <!-- The main reason for this is 1) faster/lighter; and 2) infinite scrollback (fbcon scrollback is completely gone in recent 6.x kernels!) -->
        <serial type='pty'>
          <target type='isa-serial' port='0'>
            <model name='isa-serial'/>
          </target>
        </serial>
        <emulator>/usr/bin/qemu-system-x86_64</emulator>
        <controller type='usb' index='0' model='qemu-xhci' ports='15'>
          <address type='pci' domain='0x0000' bus='0x02' slot='0x00' function='0x0'/>
        </controller>
        <controller type='pci' index='0' model='pcie-root'/>
        <controller type='pci' index='1' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='1' port='0x8'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x0' multifunction='on'/>
        </controller>
        <controller type='pci' index='2' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='2' port='0x9'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x1'/>
        </controller>
        <controller type='pci' index='3' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='3' port='0xa'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x2'/>
        </controller>
        <controller type='pci' index='4' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='4' port='0xb'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x3'/>
        </controller>
        <controller type='pci' index='5' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='5' port='0xc'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x4'/>
        </controller>
        <controller type='pci' index='6' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='6' port='0xd'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x5'/>
        </controller>
        <controller type='pci' index='7' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='7' port='0xe'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x6'/>
        </controller>
        <controller type='pci' index='8' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='8' port='0xf'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x01' function='0x7'/>
        </controller>
        <controller type='pci' index='9' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='9' port='0x10'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x0' multifunction='on'/>
        </controller>
        <controller type='pci' index='10' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='10' port='0x11'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x1'/>
        </controller>
        <controller type='pci' index='11' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='11' port='0x12'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x2'/>
        </controller>
        <controller type='pci' index='12' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='12' port='0x13'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x3'/>
        </controller>
        <controller type='pci' index='13' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='13' port='0x14'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x4'/>
        </controller>
        <controller type='pci' index='14' model='pcie-root-port'>
          <model name='pcie-root-port'/>
          <target chassis='14' port='0x15'/>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x5'/>
        </controller>
        <controller type='sata' index='0'>
          <address type='pci' domain='0x0000' bus='0x00' slot='0x1f' function='0x2'/>
        </controller>
        <controller type='virtio-serial' index='0'>
          <address type='pci' domain='0x0000' bus='0x03' slot='0x00' function='0x0'/>
        </controller>
        <console type='pty'>
          <target type='serial' port='0'/>
        </console>
        <channel type='unix'>
          <target type='virtio' name='org.qemu.guest_agent.0'/>
          <address type='virtio-serial' controller='0' bus='0' port='1'/>
        </channel>
        <input type='mouse' bus='ps2'/>
        <input type='keyboard' bus='ps2'/>
        <audio id='1' type='none'/>
        <memballoon model='virtio'>
          <address type='pci' domain='0x0000' bus='0x04' slot='0x00' function='0x0'/>
        </memballoon>
        <rng model='virtio'>
          <backend model='random'>/dev/urandom</backend>
          <address type='pci' domain='0x0000' bus='0x05' slot='0x00' function='0x0'/>
        </rng>
      </devices>
    </domain>

