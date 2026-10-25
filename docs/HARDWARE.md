# Hardware — TP-Link Archer AX23 v2

Evidence tags used throughout, consistent with the rest of this repository:

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Checked by a command whose output is shown or referenced. |
| `[SOURCE]` | Read directly from a vendor-supplied file (OEM DTB, rootfs, GPL archive). |
| `[REPORTED]` | Confirmed by a third party with physical UART access to the device (see Credits). |
| `[OPEN]` | Unknown, or a hypothesis not yet tested. |

This document covers the **v2.0** hardware revision only. The AX23 **v1** is a
different device (MediaTek MT7621, already supported upstream) and is out of scope.

## Identification

`[SOURCE]` From the OEM firmware's `product-info`:

```
vendor_name:TP-Link
product_name:Archer AX23
device_name:Wireless Router Archer AX23
country:US
product_ver:2.0.0
hw_ver:00000001
product_id:18000002
special_id:55530000
```

`special_id:55530000` corresponds to a US-market unit. Other `special_id` values seen
in the firmware's support list include EU (`4555`), CA (`4341`), and TW (`5457`) — the
hardware is presumed identical across these regions, but this has not been confirmed.

## SoC and memory

`[SOURCE]`/`[REPORTED]`

| Component | Detail |
|---|---|
| SoC | Qualcomm IPQ5018, dual-core Cortex-A53 |
| Machine ID | `0x8040000`, board reference `AP-MP02.1` |
| RAM | 256MB DDR3 — CDT string `AP-MP02.1_128M16_DDR3_LM256` |
| Flash | SPI NAND, 128MB (ESMT), dual-image (A/B) layout |
| Kernel (OEM) | Linux 4.4.60, Qualcomm fork |

## Ethernet switch

`[SOURCE]`/`[VERIFIED]`

| Component | Detail |
|---|---|
| Chip | Realtek RTL8367SC |
| Reported chip ID | `0x6642` (RTL8367D family — "family D" in Realtek's own driver naming) `[VERIFIED]` via static analysis of vendor `qca-ssdk.ko`; **not yet confirmed against a physical unit**, see `docs/KNOWN-ISSUES.md` |
| Reset GPIO | GPIO33 (shared with the 2.4GHz LED — see GPIO map below) |
| Uplink | SGMII, 1Gbps, GMAC1 → UNIPHY0 → switch CPU port 6 |
| LAN ports | 1, 2, 3, 4 |
| WAN port | 0 |
| CPU port | 6 (tagged, `6t` in OEM `/etc/config/switch`) |

`[SOURCE]` From the OEM firmware's own switch config (`/etc/config/switch`) and
`/lib/switch/core_phy.sh`:

```
LAN_PORTS="1 2 3 4"
WAN_PORTS="0"
CPU_PORTS="16"   # internal driver numbering, differs from OpenWrt's port numbering
```

A comment embedded in the OEM firmware describes the hardware as: *"switch, only
6ports: 4 LAN ports, 1 WAN port, 1 CPU port"* — consistent with the above.

**Important caveat:** detection of the switch over MDIO (confirmed by static analysis
of the vendor driver, see `docs/RESEARCH.md`) does not by itself demonstrate working
Ethernet traffic over this link. See `docs/KNOWN-ISSUES.md` §1 and §4.

## Radios

`[SOURCE]`

| Band | Chip | Interface | Driver (OpenWrt) |
|---|---|---|---|
| 2.4GHz | IPQ5018 internal | — | `ath11k` |
| 5GHz | QCN6102 (firmware: `qcn6122`) | PCIe | `ath11k` |

Board calibration data for both radios is present in the OEM rootfs independent of the
`ART` NAND partition:

```
CA/default/lib/firmware/IPQ5018/WIFI_FW/bdwlan.b24   (128KB, 2.4GHz)
CA/default/lib/firmware/IPQ5018/WIFI_FW/qcn6122/bdwlan.b60   (128KB, 5GHz)
```

The OEM `wifi_fw_mount` init script symlinks this `WIFI_FW/` directory to
`/lib/firmware/IPQ5018/` at runtime, which means Wi-Fi calibration does not strictly
depend on the `ART` partition being intact — relevant for units where `ART` may have
been erased (e.g. some ISP-branded units, per community reports).

## UART

`[SOURCE]`/`[REPORTED]` (pinout from OEM U-Boot DTB extracted by community member
`vram`, see Credits)

| Pin | GPIO |
|---|---|
| RX | GPIO28 |
| TX | GPIO29 |

- Baud: 115200 8N1
- Voltage: 1.8V (**do not connect a 3.3V or 5V adapter directly**)
- Header: JP1 on the PCB. TP-Link removed the SMD resistors populating this header at
  the factory — they must be bridged or bypassed to get a usable connection.

## GPIO map

`[SOURCE]` Extracted from the OEM U-Boot device tree blob.

| GPIO | Function |
|---|---|
| 10 | Power LED |
| 11 | 5GHz LED |
| 12 | WAN LED (orange) |
| 13 | WAN LED |
| 14 | Reset button |
| 22 | WPS LED |
| 28 | UART RX |
| 29 | UART TX |
| 32 | LAN LED |
| 33 | 2.4GHz LED **and** switch reset (shared) |
| 36 | MDC |
| 37 | MDIO |

`[OPEN]` LED polarity (active-high vs active-low) has not been confirmed. The
physical LAN1–4 port-to-silicon mapping is also unconfirmed — see
`docs/KNOWN-ISSUES.md` §5.

## NAND partition layout

`[SOURCE]`/`[VERIFIED]` Confirmed against the 1.1.2 rootfs and cross-checked by
community member `vram` over UART.

| Partition | Offset | Size | Notes |
|---|---|---|---|
| SBL1 | `0x0` | 512K | |
| MIBIB | `0x80000` | — | |
| BOOTCONFIG | `0x100000` | 256K | Writable — sysupgrade needs to write here |
| BOOTCONFIG1 | `0x140000` | 256K | Writable — sysupgrade needs to write here |
| QSEE | `0x180000` | 1M | |
| DEVCFG | `0x280000` | — | |
| CDT | `0x2c0000` | — | |
| APPSBLENV | `0x300000` | — | |
| APPSBL | `0x380000` | 1.25M | |
| ART | `0x4c0000` | 1M | May be erased on some ISP-branded units — see Radios above |
| TRAINING | `0x5c0000` | — | |
| rootfs | `0x640000` | 53M | Image A |
| rootfs_1 | `0x3bc0000` | 53M | Image B |
| tp_data | `0x7140000` | 8.25M | Candidate source for MAC addresses — see `docs/KNOWN-ISSUES.md` §3 |
| radio | `0x7980000` | 4.25M | |
| data | `0x7dc0000` | 512K | |

## Credits

Hardware identification in this document combines static analysis of OEM firmware
with physical confirmation by **vram**, a community member with UART access to a
physical unit, via OpenWrt forum thread `t/249493`. Items marked `[REPORTED]` above
reflect that collaboration; everything else was derived without physical hardware
access and should be treated as unconfirmed until independently verified.
