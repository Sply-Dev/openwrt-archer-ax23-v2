# TP-Link Archer AX23 v2 - OpenWrt port (work in progress)

[![OpenWrt target: qualcommax/ipq50xx](https://img.shields.io/badge/OpenWrt-qualcommax%2Fipq50xx-0088CC?logo=openwrt&logoColor=white)](docs/HARDWARE.md)
[![License: GPL v2](https://img.shields.io/badge/license-GPL--2.0-8B8B8B.svg)](LICENSE)

This repository tracks an in-progress OpenWrt port for the **TP-Link Archer AX23 v2**
(hardware version `v2.0`, Qualcomm IPQ5018 / 256MB RAM - not to be confused with the
AX23 v1, which is MediaTek MT7621-based and already officially supported by OpenWrt).

> **Status (2026-11-11):** The v0.2 initramfs booted from RAM on a physical AX23 v2
> through U-Boot/TFTP and reached an OpenWrt shell. The v0.3 test image has been
> built, but no v0.3 hardware result is documented here. See
> [`docs/TESTING.md`](docs/TESTING.md) for observations and remaining tests.
>
> Persistent installation and `sysupgrade` are not validated. A/B handling for this
> board is not implemented. The v0.2 RAM boot does not establish a safe flash path.

## Why this exists

The AX23 v2 uses a Qualcomm IPQ5018, 256 MB of RAM and a QCN6122-class
5 GHz radio. The related AX55 v1 has 512 MB of RAM and an RTL8367S
switch. Static analysis of the AX23 v2 OEM `qca-ssdk.ko` detection
routine and the upstream `rtl8365mb` register definitions identifies
its switch as the RTL8367S-VB family D device, chip ID `0x6642`.

This tree carries the project's pre-v7/v7 ten-patch series based on
OpenWrt PR #19644. A third party reported a stable SGMII link, VLAN
bridging and clean reboots on an EX511 v2 with the same switch ID.
The AX23 v2 has separate v0.2 hardware results described below;
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
| `patches/` | Locally maintained patches applied manually during the build, including ath11k caldata and AX23 v2 LAN/WAN defaults |

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
| Boot | v0.2 booted via U-Boot/TFTP to an OpenWrt shell on 2026-11-10. v0.3 test image built; hardware result pending. Persistent installation and `sysupgrade` remain unvalidated |
| Ethernet switch (RTL8367 family D) | v0.2 logs report RTL8367S-VB detection, DSA ports `wan` and `lan1`-`lan4`, and a 2.5 Gbit/s full-duplex CPU link with RX/TX flow control reported. After administrative activation, `lan1` reported carrier 1 once; forwarding and reliable operation of all external ports remain unverified |
| Default network roles | Patch `0002` adds the AX23 v2 board case for `lan1`-`lan4` as LAN and `wan` as WAN. It was added after the v0.2 tests and is not validated by those logs. Board-specific LAN/WAN MAC assignment remains unresolved |
| 2.4 GHz and 5 GHz Wi-Fi | Deliberately outside the v0.2 test scope. Board-data loading failed in the v0.2 logs; this does not establish the cause or compatibility status. Radio operation is unvalidated |
| LEDs / buttons | Switch reset GPIO39 and 2.4 GHz LED GPIO33 were identified from the live OEM device tree; functional OpenWrt validation remains open |
| MAC address assignment | Candidate NVMEM source identified; exact offset and runtime assignment remain unconfirmed |

The OEM running configuration uses a forced speed of 2500, and a 312.5 MHz
UNIPHY/GMAC clock was measured on stock hardware. Its DTB also contains
`phy-mode = "sgmii"`. The v0.2 OpenWrt log reports the CPU link up at 2.5 Gbit/s;
neither the OEM clock nor the log alone proves external-port traffic or actual
pause-frame exchange. See [`docs/DEVICE-TREE.md`](docs/DEVICE-TREE.md).

## Related upstream discussion

- OpenWrt forum thread `t/249493` - UART access and OEM DTB extraction by community member `vram`.
- OpenWrt forum thread `t/225168` - earlier AX23 v2 support discussion.

See `docs/CREDITS.md` for the origin of the `rtl8365mb` switch driver patches used here.

## License

Code in `target/` follows the licensing of the OpenWrt tree it patches (GPL-2.0-or-later
unless otherwise noted in the file, and unless otherwise noted in `docs/CREDITS.md` for
carried-in third-party patches). Documentation in `docs/` is original work by the
repository author, except where it describes or credits someone else's work.
