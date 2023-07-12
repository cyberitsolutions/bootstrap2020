// // NOTE: Setting this to 0 should be unnecessary because embedding a script disables the banner anyway
// //       But explicit is good since the main reason for building our own version at all is to get rid of this banner
// #undef BANNER_TIMEOUT
// #define BANNER_TIMEOUT 0

// We're not currently using IPv6, but we will eventually
#define NET_PROTO_IPV6          /* IPv6 protocol */

// Enable HTTPS
#define DOWNLOAD_PROTO_HTTPS    /* Secure Hypertext Transfer Protocol */
// Disable HTTP
// NOTE: It can sometimes look like HTTPS depends on this due to a "Operation not supported" error, it does not.
//       What's happening is it's trying to use http to get the cross-signing certs and **that** is unsupported.
//       https://ipxe.org/crypto#cross-signing_certificates
#undef  DOWNLOAD_PROTO_HTTP     /* Hypertext Transfer Protocol */

// Enable a few commands that we actually need in the base script
#define DHCP_CMD                /* DHCP management commands */
#define NTP_CMD                 /* NTP commands */
#define IMAGE_CMD               /* Image management commands */

// Required to even run the embedded script, and the followup script pulled over https
#define IMAGE_SCRIPT            /* iPXE script image support */
// Required for embedded https certs
#define IMAGE_PEM               /* PEM certificate file support */
// Required to even load and exec the kernel image
#if defined(PLATFORM_efi)
  // Breaks compilation of legacy BIOS builds
  #define IMAGE_EFI             /* EFI image support */
#elif defined(PLATFORM_pcbios)
  // Breaks compilation of EFI builds
  #define IMAGE_BZIMAGE         /* Linux bzImage image support */
#endif

// FIXME: We'll probably want to use this and start signing our binaries
#undef  IMAGE_TRUST_CMD         /* Image trust management commands */
// FIXME: Might we want this for secureboot integration?
#undef  SHIM_CMD                /* EFI shim command (or dummy command) */

// Disable a bunch of unnecessary protocols
#undef  DOWNLOAD_PROTO_FILE     /* Local filesystem access */
#undef  DOWNLOAD_PROTO_FTP      /* File Transfer Protocol */
#undef  DOWNLOAD_PROTO_SLAM     /* Scalable Local Area Multicast */
#undef  DOWNLOAD_PROTO_NFS      /* Network File System Protocol */
// NOTE: Maybe we want to keep this for some backcompat?
#undef  DOWNLOAD_PROTO_TFTP     /* Trivial File Transfer Protocol */
#undef  SANBOOT_PROTO_ISCSI     /* iSCSI protocol */
#undef  SANBOOT_PROTO_AOE       /* AoE protocol */
#undef  SANBOOT_PROTO_IB_SRP    /* Infiniband SCSI RDMA protocol */
#undef  SANBOOT_PROTO_FCP       /* Fibre Channel protocol */
#undef  SANBOOT_PROTO_HTTP      /* HTTP SAN protocol */

// FIXME: Do we maybe want to make use of HTTP auth somewhere?
//#define HTTP_AUTH_BASIC         /* Basic authentication */
//#define HTTP_AUTH_DIGEST        /* Digest authentication */
#undef  HTTP_AUTH_BASIC         /* Basic authentication */
#undef  HTTP_AUTH_DIGEST        /* Digest authentication */

// Do we want to support WiFi?
//#define CRYPTO_80211_WEP        /* WEP encryption (deprecated and insecure!) */
//#define CRYPTO_80211_WPA        /* WPA Personal, authenticating with passphrase */
//#define CRYPTO_80211_WPA2       /* Add support for stronger WPA cryptography */

// Disable a bunch of image file types we don't use
#undef  IMAGE_NBI               /* NBI image support */
#undef  IMAGE_ELF               /* ELF image support */
#undef  IMAGE_MULTIBOOT         /* MultiBoot image support */
#undef  IMAGE_PXE               /* PXE image support */
#undef  IMAGE_COMBOOT           /* SYSLINUX COMBOOT image support */
#undef  IMAGE_SDI               /* SDI image support */
#undef  IMAGE_PNM               /* PNM image support */
#undef  IMAGE_PNG               /* PNG image support */
#undef  IMAGE_DER               /* DER image support */
// Might these let us compress the kernel images? Would that be useful to us?
#undef  IMAGE_ZLIB              /* ZLIB image support */
#undef  IMAGE_GZIP              /* GZIP image support */

// Disable a bunch of unused script commands
#undef  AUTOBOOT_CMD            /* Automatic booting */
#undef  NVO_CMD                 /* Non-volatile option storage commands */
#undef  CONFIG_CMD              /* Option configuration console */
#undef  IFMGMT_CMD              /* Interface management commands */
#undef  IWMGMT_CMD              /* Wireless interface management commands */
#undef  IBMGMT_CMD              /* Infiniband management commands */
#undef  FCMGMT_CMD              /* Fibre Channel management commands */
#undef  ROUTE_CMD               /* Routing table management commands */
#undef  SANBOOT_CMD             /* SAN boot commands */
#undef  MENU_CMD                /* Menu commands */
#undef  LOGIN_CMD               /* Login command */
#undef  SYNC_CMD                /* Sync command */
#undef  NSLOOKUP_CMD            /* DNS resolving command */
#undef  TIME_CMD                /* Time commands */
#undef  DIGEST_CMD              /* Image crypto digest commands */
#undef  LOTEST_CMD              /* Loopback testing commands */
#undef  VLAN_CMD                /* VLAN commands */
#undef  PXE_CMD                 /* PXE commands */
#undef  REBOOT_CMD              /* Reboot command */
#undef  POWEROFF_CMD            /* Power off command */
#undef  PCI_CMD                 /* PCI commands */
#undef  PARAM_CMD               /* Request parameter commands */
#undef  NEIGHBOUR_CMD           /* Neighbour management commands */
#undef  PING_CMD                /* Ping command */
#undef  CONSOLE_CMD             /* Console command */
#undef  IPSTAT_CMD              /* IP statistics commands */
#undef  PROFSTAT_CMD            /* Profiling commands */
#undef  CERT_CMD                /* Certificate management commands */
#undef  IMAGE_MEM_CMD           /* Read memory command */
#undef  IMAGE_ARCHIVE_CMD       /* Archive image management commands */
#undef  SHELL_CMD               /* Shell command */
