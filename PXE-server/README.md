# PXE Network Boot Server

Boot any computer on your LAN into a Linux installer over Ethernet — no USB needed.

## How It Works

```
Client Machine                   PXE Server (this machine)
──────────────                   ──────────────────────────
BIOS/UEFI: "Boot from network"
        │
        ▼ DHCP Request (UDP 67)
        ──────────────────────► dnsmasq
                                   │  "Your IP is 192.168.1.101"
                                   │  "TFTP server is 192.168.1.10"
                                   │  "Boot file: pxelinux.0"
        ◄──────────────────────────┘
        │
        ▼ TFTP fetch pxelinux.0 (UDP 69)
        ──────────────────────► TFTP (dnsmasq built-in)
        ◄── pxelinux.0 ────────────┘
        │
        ▼ TFTP fetch boot menu
        ──────────────────────► pxelinux.cfg/default
        ◄── menu with OS list ──────┘
        │
        ▼ User picks "Rocky Linux 9"
        ──────────────────────► TFTP fetch vmlinuz + initrd
        ▼
        kernel boots, fetches installer via HTTP (port 80)
        ──────────────────────► nginx serves /var/www/pxe/
        ▼
        OS installs automatically from kickstart file
```

## Stack

| Component | Role |
|-----------|------|
| **dnsmasq** | DHCP server + TFTP server (single process) |
| **nginx** | HTTP server — serves kernels, ISO repos, kickstart files |
| **syslinux/pxelinux** | PXE bootloader loaded by client over TFTP |
| **kickstart / preseed** | Fully automated OS installation answers |

## Supported OS Installs

| OS | Type |
|----|------|
| Rocky Linux 9 (x86_64) | Automated via kickstart |
| Ubuntu 24.04 LTS (x86_64) | Automated via preseed |
| Memtest86+ | RAM diagnostic tool |

## Quick Start

### 1. Prerequisites

- A Linux server connected to the same LAN as the machines you want to boot
- Root/sudo access
- Internet access (to download kernels)
- Ports **67/udp** (DHCP), **69/udp** (TFTP), **80/tcp** (HTTP) must be free

> ⚠️ If your network already has a DHCP server (e.g. your router), you must either
> disable it or configure your router to use **proxy DHCP** (option 43/66/67).

### 2. Edit Configuration

Open `setup.sh` and set the variables at the top:

```bash
LAN_INTERFACE="eth0"          # Your LAN network interface
SERVER_IP="192.168.1.10"      # This server's static IP
DHCP_RANGE_START="192.168.1.100"
DHCP_RANGE_END="192.168.1.200"
GATEWAY="192.168.1.1"         # Your router IP
```

### 3. Run Setup

```bash
sudo bash setup.sh
```

This installs dnsmasq + nginx + syslinux, configures everything, and starts services.

### 4. Download OS Kernels

```bash
sudo bash fetch-kernels.sh
```

Downloads `vmlinuz` + `initrd` for Rocky 9 and Ubuntu 24.04 into `/var/lib/tftpboot/images/`.

### 5. (Optional) Customise Kickstart

Edit the auto-install answer files before deploying:

```bash
# Rocky Linux automated install
http/ks/rocky9-ks.cfg

# Ubuntu automated install
http/ks/ubuntu2404-preseed.cfg
```

At minimum, change the **password hashes** in both files.

### 6. Boot a Client

1. On the target machine: enter BIOS/UEFI → set **Network/PXE** as first boot device
2. Boot — the machine will get an IP from dnsmasq and show the PXE menu
3. Select your OS and press Enter

### 7. Check Status

```bash
sudo bash pxe-status.sh
```

Watch live boot activity:

```bash
tail -f /var/log/dnsmasq-pxe.log
```

---

## Project Structure

```
PXE-server/
├── setup.sh                    # Main installer script
├── fetch-kernels.sh            # Downloads OS netboot kernels
├── pxe-status.sh               # Health check / diagnostics
├── config/
│   └── dnsmasq.conf            # Reference dnsmasq config (written by setup.sh)
├── tftpboot/
│   └── pxelinux.cfg/
│       └── default             # PXE boot menu (template)
├── http/
│   └── ks/
│       ├── rocky9-ks.cfg           # Rocky 9 kickstart
│       └── ubuntu2404-preseed.cfg  # Ubuntu 24.04 preseed
└── docs/
    └── architecture.md
```

---

## UEFI Support

To support UEFI clients alongside BIOS, install `grub2-efi` and uncomment the UEFI lines in `config/dnsmasq.conf`:

```bash
# Rocky Linux
sudo dnf install -y grub2-efi-x64 shim-x64
cp /boot/efi/EFI/rocky/grubx64.efi /var/lib/tftpboot/
cp /boot/efi/EFI/rocky/shimx64.efi /var/lib/tftpboot/
```

Then in `dnsmasq.conf`:
```
dhcp-match=set:efi-x86_64,option:client-arch,7
dhcp-boot=tag:efi-x86_64,grubx64.efi
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Client gets no IP | Check `LAN_INTERFACE` in setup.sh, check if another DHCP server exists |
| PXE ROM timeout | Ensure ports 67/udp and 69/udp are open in firewall |
| `pxelinux.0` not found | Re-run setup.sh; check syslinux is installed |
| Kernel download fails | Check internet access; re-run fetch-kernels.sh |
| Install fails mid-way | Edit kickstart/preseed, ensure `SERVER_IP` was substituted correctly |

```bash
# Restart services
sudo systemctl restart dnsmasq nginx

# Check for errors
sudo journalctl -u dnsmasq -n 50
sudo journalctl -u nginx -n 50
```
