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
in the firmware's support list include EU (`4555`), CA (`4341`), and TW (`5457`), the
hardware is presumed identical across these regions, but this has not been confirmed.

## SoC and memory

`[SOURCE]`/`[REPORTED]`

| Component | Detail |
|---|---|
| SoC | Qualcomm IPQ5018, dual-core Cortex-A53 |
| Machine ID | `0x8040000`, board reference `AP-MP02.1` |
| RAM | 256MB DDR3, CDT string `AP-MP02.1_128M16_DDR3_LM256` |
| Flash | SPI NAND, 128MB (ESMT), dual-image (A/B) layout |
| Kernel (OEM) | Linux 4.4.60, Qualcomm fork |

## Ethernet switch

`[SOURCE]`/`[VERIFIED]`

| Component | Detail |
|---|---|
| Chip | Realtek RTL8367S-VB |
| Chip ID | `0x6642`, chip revision `0x0010`. `[VERIFIED]` by two independent static-analysis paths against the vendor `qca-ssdk.ko`: cross-reference with OpenWrt's legacy `rtl8367b.c` driver (`chip_num=0x6642` / `chip_ver=0x0010` maps directly to `RTL8367B_CHIP_RTL8367S_VB`), and the chip detection routine's own internal structure, which tests a separate, earlier ID set (`0x0276`, `0x0597`, `0x6367`, belonging to the unrelated RTL8367C family) before reaching the `0x6642` check that this device actually resolves to. See `docs/RESEARCH.md` for the detailed derivation. This confirms the chip as RTL8367S-VB, "family D" in Realtek's own driver naming. **Still not confirmed by reading the register on a physical unit**, see `docs/KNOWN-ISSUES.md` §1. |
| Reset GPIO | GPIO33 (shared with the 2.4GHz LED, see GPIO map below) |
| Uplink | GMAC1 → UNIPHY0 → switch CPU port 6. Link mode is an open question, see the caveat below. |
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
6ports: 4 LAN ports, 1 WAN port, 1 CPU port"*, consistent with the above.

**Uplink speed caveat `[OPEN]`:** this port's DTS currently configures the GMAC1 to
switch CPU port link as SGMII, fixed 1000Mbps. This is now disputed. The OEM U-Boot
source (`ipq5018_gmac.c`) configures `MODE_EXT_HSGMII` / `PORT_SPEED_2500M` for this
link, and production DTS files for sibling TP-Link boards on the same switch family
(AX53 v2, AX58 v2, from `kuncy7/openwrt-nss-edma`) use `2500base-x` with a 50MHz
reference clock rather than SGMII at 25MHz. The DTB extracted from this device's own
stock firmware shows `phy-mode = "sgmii"` with a fixed-link speed of 1000, matching
the current DTS, but conflicting with the U-Boot source for the same device. This
discrepancy is unresolved; see `docs/RESEARCH.md` and `docs/KNOWN-ISSUES.md` §4.

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
depend on the `ART` partition being intact, relevant for units where `ART` may have
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
  the factory, they must be bridged or bypassed to get a usable connection.

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
physical LAN1–4 port-to-silicon mapping is also unconfirmed, see
`docs/KNOWN-ISSUES.md` §5.

## NAND partition layout

`[SOURCE]`/`[VERIFIED]` Confirmed against the 1.1.2 rootfs and cross-checked by
community member `vram` over UART.

| Partition | Offset | Size | Notes |
|---|---|---|---|
| SBL1 | `0x0` | 512K | |
| MIBIB | `0x80000` | — | |
| BOOTCONFIG | `0x100000` | 256K | Read-only. Boot slot selection is handled through U-Boot environment (`fw_setenv tp_boot_idx`), not by writing this partition, see the note below. |
| BOOTCONFIG1 | `0x140000` | 256K | Read-only, same reasoning as BOOTCONFIG above. |
| QSEE | `0x180000` | 1M | |
| DEVCFG | `0x280000` | — | |
| CDT | `0x2c0000` | — | |
| APPSBLENV | `0x300000` | — | |
| APPSBL | `0x380000` | 1.25M | |
| ART | `0x4c0000` | 1M | May be erased on some ISP-branded units, see Radios above |
| TRAINING | `0x5c0000` | — | |
| rootfs | `0x640000` | 53M | Image A |
| rootfs_1 | `0x3bc0000` | 53M | Image B |
| tp_data | `0x7140000` | 8.25M | Candidate source for MAC addresses, see `docs/KNOWN-ISSUES.md` §3 |
| radio | `0x7980000` | 4.25M | |
| data | `0x7dc0000` | 512K | |

**A/B boot mechanism note:** an earlier version of this document assumed sysupgrade
needed write access to BOOTCONFIG/BOOTCONFIG1 to switch boot slots. This was
incorrect. Cross-referenced from three places in the vendor's own GPL source
(`configs/ipq5018.h`'s `BOOT_IDX_FLAG` under `CONFIG_TP_IMAGE`, `nvrammanager`'s
`nm_api.h` `TP_BOOT_IDX`, and literal strings `tp_boot_idx` / `fw_setenv %s` inside the
`nvrammanager` binary itself), the actual mechanism is `fw_setenv tp_boot_idx <0|1>`
against the U-Boot environment (stored in `APPSBLENV`), the same mechanism used by
`kuncy7`'s `platform.sh` case for the sibling `tplink,archer-ax55-v1` board. The
correct install path is writing `rootfs`/`rootfs_1` plus `fw_setenv tp_boot_idx`, with
BOOTCONFIG/BOOTCONFIG1 left read-only.

## Credits

Hardware identification in this document combines static analysis of OEM firmware
with physical confirmation by **vram**, a community member with UART access to a
physical unit, via OpenWrt forum thread `t/249493`. Items marked `[REPORTED]` above
reflect that collaboration, everything else was derived without physical hardware
access and should be treated as unconfirmed until independently verified.

The rtl8365mb switch driver patches referenced throughout this document were
not written by this project, see [CREDITS.md](CREDITS.md) for their authors.
