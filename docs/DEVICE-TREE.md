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

### Uplink speed: OEM runtime measurement and v0.2 OpenWrt log

The trunk between `gmac1` and the switch's CPU port is configured as HSGMII 2.5G
(`2500base-x`, `fixed-link` speed 2500, `uniphy0` at 50MHz). The evidence for this mode and the limits of the
v0.2 hardware observation are recorded below.

**OEM runtime evidence:** the clock measurement was obtained on physical
stock hardware. On live stock hardware, `/sys/kernel/debug/clk/
clk_summary` shows the UNIPHY/GMAC1 tx and rx clocks locked at `312,500,000 Hz`.
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

**Why the static OEM device tree blob appears to say otherwise**: the `dp2`/`gmac1`
node in the stock DTB declares `phy-mode = "sgmii"` with no `forced-speed` property
of its own (that property only exists on the switch's `port@1` node). This looked
like a contradiction within the same DTB, and was the original reason this DTS used
SGMII 1G. The `phy-mode` string alone does not specify the observed line rate. The
switch node's forced speed of 2500 and the stock clock measurement support the
HSGMII 2.5G interpretation. The exact semantics of the OEM kernel's `sgmii`
label have not been established from the DTB text alone.

**Why the OEM would run HSGMII with no single physical port above 1G**: this device
has five 1G physical ports (WAN + LAN1-4); no single port on this SKU exceeds 1G.
The leading hypothesis is that aggregate throughput across WAN + LAN + 2.4GHz/5GHz
WiFi can exceed what a 1G trunk allows even though no individual port does, and
since there is no native "1.8G" electrical mode on this SerDes/switch, HSGMII 2.5G
is a mode capable of carrying that estimated aggregate rate. This throughput estimate
has not been independently measured and is noted as the leading hypothesis, not a
proven fact. An earlier line of reasoning held that sibling TP-Link boards (AX53 v2,
AX58 v2) might use HSGMII 2.5G because they have 2.5G physical ports.
Direct inspection of those boards' production DTS files does not support
that explanation. The inspected `kuncy7/openwrt-nss-edma` DTS files
for AX53 v2 and AX58 v2 describe five 1G physical ports and an HSGMII
2.5G trunk.
Switch-side aggregation or oversubscription is a possible rationale;
it has not been measured on the AX23 v2.

**`pause` is set on both `fixed-link` nodes** (`gmac1` and the switch's `port@6`).
A third party measured, on a related board, that without `pause` in this same
over-subscription scenario (a 2.5G trunk feeding 1G physical ports), throughput
dropped from 940 to 466 Mbps with roughly 13% UDP loss, because the switch could
not backpressure the faster GMAC against the slower physical ports.
This device has a similar 2.5 Gbit/s trunk to 1 Gbit/s physical-port
arrangement, which motivates the `pause` configuration. The v0.2 log
reports RX/TX flow control on the CPU link, but it does not measure
pause frames or their effect on traffic. See `KNOWN-ISSUES.md` §10
for the inspected driver path.

**OpenWrt v0.2 observation and limits:** the serial log shows the switch
and GMAC CPU link up at 2.5 Gbit/s full duplex with RX/TX flow control
reported. This validates link reporting during an actual OpenWrt boot,
beyond the earlier OEM measurements. It does not establish reliable
forwarding through the physical ports, throughput, or effective pause
behavior. The only supplied external-port carrier result is `lan1 = 1`
after administrative activation; the v0.3 test result is pending.

### Switch node

The switch is described under `&mdio1` using the upstream `realtek,rtl8365mb` binding:

- `reg = 29` (switch MDIO address on MDIO1; physical access has not been confirmed)
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
adopted (replacing an earlier, less complete v1 revision of eight patches). Compared with v1, the current series adds family D
LUT/L2 support and generalizes the SerDes indexing
to cover family D's extension port layout. It has been tested by a third party on a
TP-Link EX511 v2, a different device sharing the same chip ID/family, with a stable
link, VLAN bridging, and clean reboot cycles reported. The v0.2 AX23 log
separately shows switch detection and a 2.5 Gbit/s CPU link; it does not
validate all external ports. See `docs/CREDITS.md` for
full authorship and `docs/KNOWN-ISSUES.md` §8 for what changed between revisions.

## Wi-Fi

- `q6v5_wcss` boot arguments are set for QCN6102 in "UPD2" mode, without this, the
  QCN6102 firmware has been observed (on the reference EX511 v2 tree) to crash
  approximately 59 seconds after boot.
- `ath11k-fw-memory-mode = 2` is set on **both** radios. This is required at 256MB of
  total RAM, higher-RAM devices on the same SoC can use a different mode.
- Wi-Fi compatibility was deliberately outside the v0.2 tests. The kernel
  attempted radio probing but board-data loading failed; this does not
  establish the cause or radio compatibility.
- The published ath11k caldata hotplug patch extracts calibration data directly from
  `0:ART` at fixed offsets (`0x1000` for 2.4 GHz and `0x26800` for 5 GHz), it does not
  use NVMEM cells declared in this DTS. Neither the offsets nor successful radio
  calibration have been validated on real hardware, see `KNOWN-ISSUES.md` §2.

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
  NVMEM cells for it. The caldata patch reads the MAC from
  `/tmp/tp_data/default-mac`; the validity of that source on this device and the
  derivation of the MAC addresses have not been confirmed on real hardware, see
  `KNOWN-ISSUES.md` §3.

## What is intentionally left as a TODO in the DTS itself

These are marked inline in the DTS with comments, and tracked with more detail in
`KNOWN-ISSUES.md`:

- LED polarity (active-high vs active-low), `KNOWN-ISSUES.md` §5
- Physical LAN1–4 port-to-silicon label mapping, `KNOWN-ISSUES.md` §5
- Exact MAC offset within `tp_data`, `KNOWN-ISSUES.md` §3
- Exact calibration-variant string for the switch family, `KNOWN-ISSUES.md` §1
- Effective pause-frame exchange and traffic under load on the HSGMII
  2.5G trunk; see `KNOWN-ISSUES.md` §10

These items do not block a build or negate the v0.2 RAM boot. They limit
claims about complete device support; see `TESTING.md` for the current state.
