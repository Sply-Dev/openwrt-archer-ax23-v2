# Hardware: TP-Link Archer AX23 v2

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

`[SOURCE]`/`[VERIFIED]`/`[REPORTED]`

| Component | Detail |
|---|---|
| Chip | Realtek RTL8367S-VB |
| Chip ID | `0x6642`, chip revision `0x0010`. `[VERIFIED]` by static analysis of vendor `qca-ssdk.ko` and runtime probe by the `rtl8365mb` driver over MDIO (`rtl8365mb-mdio: found an RTL8367S-VB switch`). This confirms the chip as RTL8367S-VB, "family D" in Realtek's naming. |
| Reset GPIO | GPIO39, read from the live OEM device tree; GPIO33 is the 2.4 GHz LED |
| Uplink | GMAC1 → UNIPHY0 → switch CPU port 6. Configured as HSGMII 2.5G (`2500base-x`) with flow control. Verified up at 2.5 Gbps in OpenWrt boots. |
| LAN ports | 1, 2, 3, 4 (`[REPORTED]` `br-lan` membership and LAN-to-LAN forwarding verified in v0.3) |
| WAN port | 0 (`[REPORTED]` 1 Gbps physical link negotiation and external ping verified in v0.4-2 / v0.4-3) |
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

**Uplink evidence:** on running OEM hardware, UNIPHY/GMAC TX and RX
clocks were measured at 312.5 MHz. The OEM DTB says
`phy-mode = "sgmii"` on the GMAC side and gives the switch
`port@1` `forced-speed = <0x9c4>` (2500) and
`forced-duplex = <1>`. The U-Boot source also configures
`MODE_EXT_HSGMII` / `PORT_SPEED_2500M`. The current OpenWrt DTS uses
`2500base-x` with speed 2500 and `pause`. OpenWrt boot logs report
the CPU link up at 2.5 Gbit/s full duplex with RX/TX flow control.

**Hardware validation:** Physical testing through v0.4-3 confirmed:
- Switch detection and CPU link up at 2.5 Gbps / Full.
- LAN ports 1–4 operational under `br-lan` bridge with LAN-to-LAN packet forwarding (v0.3).
- WAN port negotiating at 1Gbps/Full with successful external ICMP ping from the router (v0.4-2 / v0.4-3).
- Client LAN-to-WAN NAT forwarding validation remains pending.

## Radios

`[SOURCE]`

| Band | Chip | Interface | Driver (OpenWrt) |
|---|---|---|---|
| 2.4GHz | IPQ5018 internal | Not specified | `ath11k` |
| 5GHz | QCN6102 (firmware: `qcn6122`) | PCIe | `ath11k` |

Board calibration data for both radios is present in the OEM rootfs independent of the
`ART` NAND partition:

```
CA/default/lib/firmware/IPQ5018/WIFI_FW/bdwlan.b24   (128KB, 2.4GHz)
CA/default/lib/firmware/IPQ5018/WIFI_FW/qcn6122/bdwlan.b60   (128KB, 5GHz)
```

The OEM `wifi_fw_mount` init script symlinks this `WIFI_FW/` directory to
`/lib/firmware/IPQ5018/` at runtime. Offsets in the `ART` NAND partition (`0x1000` for 2.4 GHz and `0x26800` for 5 GHz) were confirmed bit-for-bit against hardware partition dumps. Runtime radio bring-up is currently blocked by ath11k failing to fetch board data (error `-12`).

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

`[SOURCE]`/`[VERIFIED]` Extracted from OEM device tree and verified on physical hardware.

| GPIO | Function | Polarity |
|---|---|---|
| 10 | Power LED | `GPIO_ACTIVE_HIGH` |
| 11 | 5GHz LED | `GPIO_ACTIVE_HIGH` |
| 12 | WAN LED (orange) | `GPIO_ACTIVE_HIGH` |
| 13 | WAN LED (green/white) | `GPIO_ACTIVE_HIGH` |
| 14 | Reset button | Active-low |
| 22 | WPS LED | `GPIO_ACTIVE_HIGH` |
| 28 | UART RX | N/A |
| 29 | UART TX | N/A |
| 32 | LAN LED | `GPIO_ACTIVE_HIGH` |
| 33 | 2.4 GHz LED | `GPIO_ACTIVE_HIGH` |
| 39 | Switch reset | Active-low |
| 36 | MDC | N/A |
| 37 | MDIO | N/A |

`[VERIFIED]`/`[REPORTED]` All 7 LED nodes were confirmed `GPIO_ACTIVE_HIGH` from the live OEM device tree and physical testing (v0.4). LAN and WAN `netdev` link/activity triggers were confirmed working in v0.4-2. Physical LAN1–4 port mapping was confirmed working under `br-lan` in v0.3.

## NAND partition layout

`[SOURCE]`/`[VERIFIED]` Confirmed against the 1.1.2 rootfs and cross-checked by
community members over UART.

| Partition | Offset | Size | Notes |
|---|---|---|---|
| SBL1 | `0x0` | 512K | |
| MIBIB | `0x80000` | Not specified | |
| BOOTCONFIG | `0x100000` | 256K | Read-only. Boot slot selection is handled through U-Boot environment (`fw_setenv tp_boot_idx`), not by writing this partition, see the note below. |
| BOOTCONFIG1 | `0x140000` | 256K | Read-only, same reasoning as BOOTCONFIG above. |
| QSEE | `0x180000` | 1M | |
| DEVCFG | `0x280000` | Not specified | |
| CDT | `0x2c0000` | Not specified | |
| APPSBLENV | `0x300000` | Not specified | |
| APPSBL | `0x380000` | 1.25M | |
| ART | `0x4c0000` | 1M | MAC fields are erased `0xFF` by factory design; caldata at `0x1000` and `0x26800` |
| TRAINING | `0x5c0000` | Not specified | |
| rootfs | `0x640000` | 53M | Image A |
| rootfs_1 | `0x3bc0000` | 53M | Image B |
| tp_data | `0x7140000` | 8.25M | `[VERIFIED]` UBIFS volume containing `default-mac`, mounted during preinit (v0.4-3) |
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
with physical confirmation by **vram** and **Veraxis**, community members with UART
access to physical units, via OpenWrt forum threads `t/249493` and `t/254876`. Items
marked `[REPORTED]` above reflect that collaboration. Subsequent OEM runtime measurements
and OpenWrt serial logs are described in the relevant sections.

The rtl8365mb switch driver patches referenced throughout this document were
not written by this project, see [CREDITS.md](CREDITS.md) for their authors.
