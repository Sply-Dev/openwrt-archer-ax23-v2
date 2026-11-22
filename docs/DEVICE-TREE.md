# Device tree: design notes

This document explains the decisions behind
[`target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts`](../target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts),
not the raw hardware facts, those are in [`HARDWARE.md`](HARDWARE.md). Evidence tags
are the same as elsewhere in this repository.

## Base and references

The DTS is built on `ipq5018.dtsi` + `ipq5018-ess.dtsi` + `ipq5018-qcn6122.dtsi`,
following the subtarget base used by devices already supported upstream on the same SoC.
(Note: `ipq5018-nss.dtsi` is not included in this device tree; NSS hardware acceleration
regions are not configured here).

Two existing OpenWrt device trees were used as direct references:

- **EX511 v2** (`kuncy7/openwrt-nss-edma`, branch `ipq50xx-nss`), same SoC, same RAM
  size (256MB), same ath11k/QCN6102 radio configuration. Used as the template for the
  radio nodes and memory-saving parameters (`ath11k-fw-memory-mode = 2`, QCN6102 boot-args).
- **AX55 v1** (`kuncy7/openwrt-ax55-v1`), closest available reference for a TP-Link
  IPQ50xx device using an RTL8367-family switch over SGMII with a `tp_data`-sourced
  MAC address. Used as the template for SerDes/SGMII configuration, the general switch
  binding pattern, and the `tp_data` MAC convention also used in the caldata patch (see
  `KNOWN-ISSUES.md` for the caldata patch itself).

Neither reference device is identical to the AX23 v2, both required adaptation, not
a straight copy. Where a value was copied from a reference rather than derived from
this device's own OEM data, that is noted below.

Note: the AX55 v1 reference is on the switch's "family C" (RTL8367S), not "family D"
(RTL8367S-VB) like the AX23 v2, see the Switch node section below. The SGMII/SerDes
binding pattern was still usable as a template, but the family-specific driver logic
is not shared between the two boards' patch sets.

## Memory and bootargs

`256MB` total RAM (see `HARDWARE.md`) is below what most `ipq50xx` devices in the
upstream tree ship with (many have 512MB or 1GB). In this DTS:

- `chosen { bootargs-append = " root=/dev/ubiblock0_1 coherent_pool=2M"; };` sets the
  root device to `/dev/ubiblock0_1` and the coherent DMA pool to 2MB. This records
  the configured boot argument, its runtime impact has not been validated on
  physical hardware. `root=/dev/ubiblock0_1` is the standard pattern across
  `qualcommax/ipq50xx` SPI-NAND devices (AX55 v1, AX850, WRC-X3000GS2, and others):
  the kernel attaches the `rootfs` NAND partition as a UBI volume at runtime, and
  `ubiblock0_1` is the block device exposed after that attach. It is not specific to
  this device and not a leftover from a different device profile.
- No explicit NSS memory reservation (`nss_region`) is declared.

This constrained RAM size is also the reason this device is not expected to be accepted into
OpenWrt mainline in its current form, see `KNOWN-ISSUES.md` §6.

## Ethernet

- `gmac0` is disabled, the hardware does not use it (see `HARDWARE.md`, Ethernet
  switch table: only `gmac1` is wired to the switch).
- `gmac1` is configured as HSGMII, 2.5G, `fixed-link`, with `pause` set. See the
  dedicated section below for the evidence behind this and why it differs from the
  OEM device tree blob's static `phy-mode` string.
- `uniphy0` uses `REFCLK_50MHZ`, matching the current HSGMII 2.5G configuration.
- `mdio0` is enabled with no static child nodes populated.
- `mdio1` is enabled using pin controller `mdio1_pins` (GPIO36 MDC, GPIO37 MDIO),
  where the switch node `switch@1d` is attached.

### Uplink speed: OEM runtime measurement and hardware observations

The trunk between `gmac1` and the switch's CPU port is configured as HSGMII 2.5G
(`2500base-x`, `fixed-link` speed 2500, `uniphy0` at 50MHz). The evidence for this mode and the hardware observations are recorded below.

**OEM runtime evidence:** the clock measurement was obtained on physical
stock hardware. On live stock hardware, `/sys/kernel/debug/clk/clk_summary` shows the UNIPHY/GMAC1 tx and rx clocks locked at `312,500,000 Hz`.
This is the exact line rate for HSGMII 2500Base-X (312.5 MHz x 10-bit 8b/10b = 3.125
Gbps). SGMII 1G would read 125 MHz. The measured frequency is a runtime observation, distinct from the
terminology used in the OEM DTB.

This measurement is corroborated by two further points:

- The stock kernel's `running.dts` (the configuration that actually governs runtime
  behaviour, not U-Boot's early generic bring-up) sets `forced-speed = <0x9c4>`
  (2500) on the switch's `port@1` node.
- The OEM U-Boot source for this device (`ipq5018_gmac.c`) configures
  `MODE_EXT_HSGMII` with `PORT_SPEED_2500M` for this same link, and prints
  `"Set RTL8367S SGMII 2.5Gbps"` during bring-up.

**Hardware validation:** On physical hardware running OpenWrt, the CPU link comes up cleanly at 2.5 Gbps (`Link is Up - 2.5Gbps/Full - flow control rx/tx`). Subsequent testing through v0.4-3 confirmed `br-lan` membership and LAN-to-LAN forwarding (v0.3), as well as physical WAN Gigabit negotiation and external connectivity from the router (v0.4-2 / v0.4-3). Client LAN-to-WAN NAT forwarding validation remains pending.

### Switch node

The switch is described under `&mdio1` using the upstream `realtek,rtl8365mb` binding:

- `reg = 29` (switch MDIO address on MDIO1)
- `reset-gpios` = GPIO39. This was corrected from an earlier GPIO33 assumption; see
  `HARDWARE.md`'s GPIO table for the evidence (GPIO39 was read directly from the
  live device tree on real hardware, GPIO33 is confirmed to be the 2.4GHz LED with
  no reset function)
- Internal MDIO bus (`realtek,smi-mdio`) declaring internal PHYs `ethernet-phy@0` through `@4`
- Individual port nodes for `port@0`–`port@4` (the four LAN ports plus WAN), and CPU port
  at `port@6` linked to `&gmac1`
- Note: `realtek,headerless-cpu-port` is **not** set in this DTS.

The chip has been identified by static analysis, with two independent lines of
evidence, as RTL8367S-VB ("family D" in Realtek's own driver naming), chip ID
`0x6642`, chip revision `0x0010`. See `HARDWARE.md`'s Ethernet switch section and
`docs/RESEARCH.md` for the derivation. Family D support itself is not upstream, it
is provided by the ten local patches in
`target/linux/generic/pending-6.18/777-01` through `777-10`, described in their own
commit messages. This DTS assumes those patches are applied, it will not build
cleanly against a stock `rtl8365mb` driver.

These local patches are the project's pre-v7/v7 `net-next` switch-driver series
tracked upstream as draft PR `openwrt/openwrt#19644`, which this tree has already
adopted (replacing an earlier, less complete v1 revision of eight patches).

## Wi-Fi

- `q6v5_wcss` boot arguments are set for QCN6102 in "UPD2" mode, without this, the
  QCN6102 firmware has been observed (on the reference EX511 v2 tree) to crash
  approximately 59 seconds after boot.
- `ath11k-fw-memory-mode = 2` is set on **both** radios. This is required at 256MB of
  total RAM, higher-RAM devices on the same SoC can use a different mode.
- Wi-Fi compatibility was deliberately outside early testing.
- The published ath11k caldata hotplug patch extracts calibration data directly from
  `0:ART` at fixed offsets (`0x1000` for 2.4 GHz and `0x26800` for 5 GHz), which were
  validated bit-for-bit against raw factory partitions extracted from hardware. However,
  runtime radio initialization currently fails during ath11k board data fetching
  (error `-12`); see `KNOWN-ISSUES.md` §2.

## NAND and boot slot selection

- `BOOTCONFIG` and `BOOTCONFIG1` **are** marked read-only in this DTS. An earlier
  design assumption held that sysupgrade needed write access to these partitions to
  switch boot slots, this was incorrect and has been corrected. The actual A/B boot
  mechanism on this device is `fw_setenv tp_boot_idx <0|1>` against the U-Boot
  environment (stored in `APPSBLENV`), confirmed from three places in the vendor's
  own GPL source, see `HARDWARE.md`'s NAND partition layout section for the detail.
  `BOOTCONFIG`/`BOOTCONFIG1` do not need to be writable for boot slot switching under
  this mechanism.
- `tp_data` is declared as a NAND partition in the DTS, but the DTS does not declare
  NVMEM cells for it (the ART partition's MAC area is erased `0xFF` in flash). Instead,
  `09_mount_tp_data` mounts `tp_data` during preinit, and `ipq50xx_setup_macs` reads the
  MAC from `/tmp/tp_data/default-mac`. This was fully confirmed on physical hardware in
  v0.4-3, producing clean MAC addresses matching the unit label.

## Status of prior DTS TODOs

Several items previously tracked as open DTS questions have been resolved through
hardware testing and forensics:

- **LED polarity:** Resolved. Live stock device tree reads confirmed all 7 LED nodes
  use `GPIO_ACTIVE_HIGH`. Polarity and `netdev` link/activity triggers were confirmed
  on physical hardware (v0.4/v0.4-2).
- **Factory MAC source:** Resolved. Reversing `appsbl.bin` confirmed ART contains no MAC
  data on this platform. The 6-byte factory MAC is read from `/tmp/tp_data/default-mac`
  and validated on physical hardware (v0.4-3).
- **Physical LAN mapping:** Resolved. `br-lan` bridge membership and physical forwarding
  were confirmed working on real hardware (v0.3).
- **Trunk lock on cold boot:** Resolved in v0.5. `[REPORTED]` by Veraxis on physical
  hardware (2026-11-20): the EXT0/SDS0 trunk locked at 2.56 s, with 3/3 cold boots and
  2/2 soft reboots clean after the UNIPHY PCS preconfiguration (patch `0006`).
  See [`TESTING.md`](TESTING.md).

**Remaining open items:**
- Investigation of the ath11k board data fetch failure (error `-12`).
- Persistent flash installation and dual-boot A/B handling via `platform.sh`.
