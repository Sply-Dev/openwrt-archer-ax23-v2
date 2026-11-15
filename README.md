# TP-Link Archer AX23 v2 - OpenWrt port (work in progress)

[![OpenWrt target: qualcommax/ipq50xx](https://img.shields.io/badge/OpenWrt-qualcommax%2Fipq50xx-0088CC?logo=openwrt&logoColor=white)](docs/HARDWARE.md)
[![License: GPL v2](https://img.shields.io/badge/license-GPL--2.0-8B8B8B.svg)](LICENSE)

This repository tracks an in-progress OpenWrt port for the **TP-Link Archer AX23 v2**
(hardware version `v2.0`, Qualcomm IPQ5018 / 256MB RAM - not to be confused with the
AX23 v1, which is MediaTek MT7621-based and already officially supported by OpenWrt).

> **Status (2026-11-15): v0.4-3-test validated on physical hardware.** The port boots
> from RAM via U-Boot/TFTP. The factory MAC address is now automatically read from
> `tp_data/default-mac` during preinit and correctly assigned to `br-lan` and `wan`
> (matching the router label). LAN and WAN `netdev` LED triggers have been confirmed
> working on physical hardware. Direct WAN external connectivity has been verified
> from the router. See [`docs/TESTING.md`](docs/TESTING.md) for the full test log.
>
> Persistent installation to NAND flash and `sysupgrade` are not validated. LAN client
> routing/NAT, Wi-Fi radio operation, and A/B boot handling remain unvalidated.


<div align="center">
  <img src="docs/img/IMG_20250218_223854_762.jpg" alt="Archer AX23 v2.0 board overview" width="600">
  <p><strong>Archer AX23 v2.0 PCB overview</strong> - Photo credit: <a href="https://forum.openwrt.org/u/nihilokrat">Nihilokrat</a> via OpenWrt forum thread <a href="https://forum.openwrt.org/t/adding-openwrt-support-for-tp-link-archer-ax23v2/225168">t/225168</a></p>
</div>


## Why this exists

The AX23 v2 uses a Qualcomm IPQ5018, 256 MB of RAM and a QCN6122-class
5 GHz radio. The related AX55 v1 has 512 MB of RAM and an RTL8367S
switch. Static analysis of the AX23 v2 OEM `qca-ssdk.ko` detection
routine and the upstream `rtl8365mb` register definitions identifies
its switch as the RTL8367S-VB family D device, chip ID `0x6642`.

This tree carries the project's pre-v7/v7 ten-patch series based on
OpenWrt PR #19644. A third party reported a stable SGMII link, VLAN
bridging and clean reboots on an EX511 v2 with the same switch ID.
The AX23 v2 has separate hardware results described below;
the EX511 v2 report does not validate this board.

<div align="center">
  <img src="docs/img/hardware-topology.svg" alt="Hardware topology: IPQ5018 SoC connected via HSGMII 2.5G to the RTL8367SC switch, which exposes 5 Ethernet ports; both radios connect to the SoC; NAND below">
</div>

## Repository layout

| Path | Contents |
|---|---|
| `docs/HARDWARE.md` | SoC, RAM, flash, switch, radios, GPIO map, NAND partition layout |
| `docs/BUILD.md` | How to reproduce the build from this tree |
| `docs/DEVICE-TREE.md` | Walkthrough of the device tree and the decisions behind it |
| `docs/RESEARCH.md` | Vendor firmware / kernel module analysis that informed the port |
| `docs/FIRMWARE-EXTRACTION-METHOD.md` | How the vendor firmware image itself was unpacked (signature, decryption, UBI/FIT/SquashFS) - the pipeline that made `RESEARCH.md` possible |
| `docs/TESTING.md` | What has and hasn't been tested, and how to test it |
| `docs/KNOWN-ISSUES.md` | Open problems, unknowns, and licensing notes |
| `docs/archer-ax23-v2-port-status.md` | Point-in-time status snapshot with evidence tags |
| `docs/CREDITS.md` | Who wrote what - this project's own work vs. carried-in third-party patches |
| `target/` | DTS, image definition snippet, and carried-in switch driver patches for this device |
| `patches/` | Locally maintained patches applied manually during the build, including ath11k caldata and AX23 v2 board defaults |

## What is and isn't here

**Included:** our own device tree, our own image definition and caldata hotplug patch,
documentation, and OEM-vs-OpenWrt comparisons - each conclusion tagged with where it
came from (GPL source, vendor firmware inspection, upstream code, or our own testing).
The `rtl8365mb` switch driver patches under `target/linux/generic/pending-6.18/` are
**not this project's own work** - they are carried in from upstream patch submissions
by their original authors; see `docs/CREDITS.md` for who wrote what. This repo also
includes a method-level description of how the vendor firmware image was unpacked (see
`docs/FIRMWARE-EXTRACTION-METHOD.md`) - described at the mechanism level, without any
recovered key material.

**Not included, on purpose:** OEM firmware images, decrypted rootfs, partition dumps,
config backups, any keys/credentials/tokens, personal data, or logs containing real
MAC addresses or other identifiers. GPL coverage of the kernel and some drivers does
not extend to the rest of the vendor firmware, so none of that is redistributed here.
See `docs/KNOWN-ISSUES.md` for a specific note on GPL source completeness for one
vendor-supplied kernel module.

## Hardware support matrix (summary)

| Component | Status |
|---|---|
| Boot | Confirmed on physical hardware through v0.4-3 via U-Boot/TFTP (RAM boot only). Persistent installation to flash and `sysupgrade` remain unvalidated |
| Ethernet switch (RTL8367 family D) | Switch detected and initialized successfully. CPU link established at 2.5 Gbps (HSGMII trunk confirmed from four independent sources). `br-lan` membership and LAN-to-LAN forwarding confirmed on physical hardware (v0.3). Direct WAN external connectivity confirmed on physical hardware through successful external ping tests from the router (v0.4-2 / v0.4-3). LAN client routing and NAT forwarding validation remains pending |
| Default network roles | Factory MAC retrieval and network interface assignment implemented and verified on physical hardware (v0.4-3). Following the preinit mount fix, `tp_data` is automatically mounted and the factory MAC from `default-mac` is correctly assigned to `br-lan` and `wan` (MAC+1), matching the router label |
| 2.4 GHz and 5 GHz Wi-Fi | Board-data loading fails with error `-12` in current builds; root cause unknown. Radio operation is unvalidated |
| LEDs / buttons | All 7 LED nodes confirmed `GPIO_ACTIVE_HIGH` from live OEM device tree. LAN and WAN `netdev` link/activity triggers confirmed working on physical hardware (v0.4-2). Amber WAN LED connectivity logic (OEM `ledctrl` daemon) is a known limitation - not implemented |
| MAC address assignment | Resolved and verified on physical hardware (v0.4-3). U-Boot leaves ART MAC fields as erased flash (`0xFF`). Factory MAC resides in `tp_data/default-mac`; preinit script mounts `tp_data` automatically at boot, correctly populating `br-lan` and `wan` without manual intervention |

The OEM running configuration uses a forced speed of 2500, and a 312.5 MHz
UNIPHY/GMAC clock was measured on stock hardware. Its DTB also contains
`phy-mode = "sgmii"`. The HSGMII 2.5 Gbit/s CPU trunk is confirmed from four
independent sources; see [`docs/DEVICE-TREE.md`](docs/DEVICE-TREE.md) for details.

## Related upstream discussion

- OpenWrt forum thread `t/254876` - active development thread for this port (v0.2 onward), including hardware test results from community tester Veraxis.
- OpenWrt forum thread `t/249493` - UART access and OEM DTB extraction by community member `vram`.
- OpenWrt forum thread `t/225168` - earlier AX23 v2 support discussion.

See `docs/CREDITS.md` for the origin of the `rtl8365mb` switch driver patches used here.

## License

Code in `target/` follows the licensing of the OpenWrt tree it patches (GPL-2.0-or-later
unless otherwise noted in the file, and unless otherwise noted in `docs/CREDITS.md` for
carried-in third-party patches). Documentation in `docs/` is original work by the
repository author, except where it describes or credits someone else's work.
