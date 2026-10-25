# Device tree — design notes

This document explains the decisions behind
[`target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts`](../target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts),
not the raw hardware facts — those are in [`HARDWARE.md`](HARDWARE.md). Evidence tags
are the same as elsewhere in this repository.

## Base and references

The DTS is built on `ipq5018.dtsi` + `ipq5018-ess.dtsi` + `ipq5018-qcn6122.dtsi`,
following the subtarget base used by devices already supported upstream on the same SoC.
(Note: `ipq5018-nss.dtsi` is not included in this device tree; NSS hardware acceleration
regions are not configured here).

Two existing OpenWrt device trees were used as direct references:

- **EX511 v2** (`kuncy7/openwrt-nss-edma`, branch `ipq50xx-nss`) — same SoC, same RAM
  size (256MB), same ath11k/QCN6102 radio configuration. Used as the template for the
  radio nodes and memory-saving parameters (`ath11k-fw-memory-mode = 2`, QCN6102 boot-args).
- **AX55 v1** (`kuncy7/openwrt-ax55-v1`) — closest available reference for a TP-Link
  IPQ50xx device using an RTL8367-family switch over SGMII with a `tp_data`-sourced
  MAC address. Used as the template for SerDes/SGMII configuration, the general switch
  binding pattern, and the `tp_data` MAC convention also used in the caldata patch (see
  `KNOWN-ISSUES.md` for the caldata patch itself).

Neither reference device is identical to the AX23 v2 — both required adaptation, not
a straight copy. Where a value was copied from a reference rather than derived from
this device's own OEM data, that is noted below.

## Memory and bootargs

`256MB` total RAM (see `HARDWARE.md`) is below what most `ipq50xx` devices in the
upstream tree ship with (many have 512MB or 1GB). In this DTS:

- `chosen { bootargs-append = " root=/dev/ubiblock0_1 coherent_pool=2M"; };` sets the
  root device to `/dev/ubiblock0_1` and the coherent DMA pool to 2MB. This records
  the configured boot argument; its runtime impact has not been validated on
  physical hardware.
- No explicit NSS memory reservation (`nss_region`) is declared.

This constrained RAM size is also the reason this device is not expected to be accepted into
OpenWrt mainline in its current form — see `KNOWN-ISSUES.md` §6.

## Ethernet

- `gmac0` is disabled — the hardware does not use it (see `HARDWARE.md`, Ethernet
  switch table: only `gmac1` is wired to the switch).
- `gmac1` is configured as SGMII, 1G, `fixed-link`, matching the OEM switch
  configuration's CPU port (port 6, tagged).
- `uniphy0` uses `REFCLK_25MHZ`.
- `mdio0` is enabled with no static child nodes populated.
- `mdio1` is enabled using pin controller `mdio1_pins` (GPIO36 MDC, GPIO37 MDIO),
  where the switch node `switch@1d` is attached.

### Switch node

The RTL8367SC is described under `&mdio1` using the upstream `realtek,rtl8365mb` binding:

- `reg = 29` (switch MDIO address on MDIO1; physical access has not been confirmed)
- `reset-gpios` = GPIO33, matching the shared LED/reset GPIO in `HARDWARE.md`
- Internal MDIO bus (`realtek,smi-mdio`) declaring internal PHYs `ethernet-phy@0` through `@4`
- Individual port nodes for `port@0`–`port@4` (the four LAN ports plus WAN), and CPU port
  at `port@6` linked to `&gmac1` over SGMII (fixed-link 1G)
- Note: `realtek,headerless-cpu-port` is **not** set in this DTS.

The "family D" (RTL8367D) switch support itself is not upstream — it is provided by
the eight local patches in `target/linux/generic/pending-6.18/777-01` through
`777-08`, described in their own commit messages. This DTS assumes those patches are
applied; it will not build cleanly against a stock `rtl8365mb` driver.

## Wi-Fi

- `q6v5_wcss` boot arguments are set for QCN6102 in "UPD2" mode — without this, the
  QCN6102 firmware has been observed (on the reference EX511 v2 tree) to crash
  approximately 59 seconds after boot.
- `ath11k-fw-memory-mode = 2` is set on **both** radios. This is required at 256MB of
  total RAM; higher-RAM devices on the same SoC can use a different mode.
- The published ath11k caldata hotplug patch extracts calibration data directly from
  `0:ART` at fixed offsets (`0x1000` for 2.4 GHz and `0x26800` for 5 GHz); it does not
  use NVMEM cells declared in this DTS. Neither the offsets nor successful radio
  calibration have been validated on real hardware — see `KNOWN-ISSUES.md` §2.

## NAND and sysupgrade

- `BOOTCONFIG` and `BOOTCONFIG1` are **not** marked read-only, unlike some reference
  trees. This is deliberate: sysupgrade needs write access to these partitions on this
  device (see `HARDWARE.md`'s partition table — both are listed as writable for this
  reason).
- `tp_data` is declared as a NAND partition in the DTS, but the DTS does not declare
  NVMEM cells for it. The caldata patch reads the MAC from
  `/tmp/tp_data/default-mac`; the validity of that source on this device and the
  derivation of the MAC addresses have not been confirmed on real hardware — see
  `KNOWN-ISSUES.md` §3.

## What is intentionally left as a TODO in the DTS itself

These are marked inline in the DTS with comments, and tracked with more detail in
`KNOWN-ISSUES.md`:

- LED polarity (active-high vs active-low) — `KNOWN-ISSUES.md` §5
- Physical LAN1–4 port-to-silicon label mapping — `KNOWN-ISSUES.md` §5
- Exact MAC offset within `tp_data` — `KNOWN-ISSUES.md` §3
- Exact calibration-variant string for the switch family — `KNOWN-ISSUES.md` §1

None of these block a build. All of them block calling this port "working" on real
hardware — see `archer-ax23-v2-port-status.md` for the current overall state.
