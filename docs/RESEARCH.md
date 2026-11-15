# Research notes: vendor firmware and `qca-ssdk.ko` analysis

This document summarizes the reverse-engineering work that informed this port's
switch driver patches (`target/linux/generic/pending-6.18/777-01` through `777-10`) and
device tree (`ipq5018-archer-ax23-v2.dts`). Evidence tags are the same as elsewhere
in this repository:

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Checked by a command whose output is shown or referenced. |
| `[SOURCE]` | Read directly from a vendor-supplied file (OEM DTB, rootfs, GPL archive). |
| `[OPEN]` | Unknown, or a hypothesis not yet tested. |

**What this document is not:** it does not include the `qca-ssdk.ko` binary, its
Ghidra decompilation, or any other extracted firmware artifact. See
`KNOWN-ISSUES.md` §7 for why. Every finding below is reported as prose/tables with
its method of derivation; no binary or decompiled source is reproduced beyond short,
individually-cited disassembly excerpts used to support a specific factual claim.

## Provenance: how this analysis became possible

This port did not start from the device tree outward. It started from a full,
independent reverse-engineering effort against the OEM firmware image itself,
which is what made the switch driver analysis below possible in the first place.
That broader effort is out of scope for this repository and is **not**
reproduced here, but it is worth naming at the method level, since it explains
where `qca-ssdk.ko` and the GPL source cross-reference below actually came from:

1. The vendor's `.bin` firmware image is signed (RSA-2048, PSS/SHA-256) and its
   payload is encrypted (AES-128-CBC); the decryption key material is itself
   derived from the RSA-PSS verification salt, following a mechanism present in
   TP-Link's own published GPL source for this device (`nvrammanager`
   component). Decrypting the payload yields a UBI image.
2. The UBI image contains two volumes: a `kernel` volume (an ARM FIT image
   wrapping a Linux 4.4.60 kernel and multiple candidate device trees) and an
   `ubi_rootfs` volume (a SquashFS/XZ root filesystem). Extracting these is
   what exposed `qca-ssdk.ko` and the rest of the rootfs used throughout this
   document.

This is described here only at the level of *which mechanism is used and where
in the pipeline it sits*, not the specific key, IV, or other artifact-specific
material recovered during that process, and not the decrypted firmware/rootfs
itself. None of that is included in this repository: it was not produced by
this project's own work, and redistributing it is unnecessary for anyone to
independently reproduce the same result from TP-Link's own public firmware
download, by the same method, on their own analysis environment.

## Method

Two independent sources were used and cross-checked against each other wherever
possible:

1. **Static disassembly** of the vendor `qca-ssdk.ko` (firmware 1.1.2, SHA-256
   `ae465c568e64099df1304183883c5c6e0b4da13eb357a6370819704a6bb70f96`, see
   `KNOWN-ISSUES.md` §7 for both known `.ko` hashes), via `readelf -s` for symbol
   offsets and `objdump -d` for instruction-level disassembly.
2. **GPL source cross-reference** against TP-Link's own `GPL_AX23v2.tar.gz` release
   for this device, specifically `chip.c` and `rtl8367d_smi.c` under
   `qca/src/u-boot-2016/drivers/net/rtl8367sc/`. This source predates and is not
   identical to the `.ko` build (see "Caveats" below), but shares enough structure
   to identify functions by behavior rather than by symbol name, since the shipped
   `.ko` has stripped/obfuscated local symbols (e.g. `_5593`, `_5398`).

A finding is marked `[VERIFIED]` only where the disassembly's register values,
call sequence, and branch structure match the corresponding GPL source function
closely enough to identify them as the same routine. Where only one of the two
sources was available, or where a value could not be confirmed in either, this is
stated explicitly rather than inferred.

## Chip detection (`switch_probe`)

`[VERIFIED]` The chip-detection routine is implemented once in GPL source
(`chip.c`, function `switch_probe`) but compiles into two near-identical blocks in
the shipped `.ko` (one per switch family, RTL8367C-and-related first, RTL8367D
second), matching the `#if defined(CONFIG_DAL_RTL8367C)` / `#if
defined(CONFIG_DAL_RTL8367D)` split in source. In the `.ko`, this is symbol `_5593`
at offset `0x43f0` (352 bytes); its caller, `hal_find_device` (`_2936` at `0x4550`),
dispatches to a per-chip control-structure table based on the detected type.

The detection sequence, identical in structure for both families and confirmed
byte-for-byte between source and disassembly:

1. Unlock: write `0x0249` to register `0x13C2`.
2. Read chip ID from register `0x1300`.
3. Read chip revision from register `0x1301`.
4. Lock: write `0x0000` to register `0x13C2`.

For RTL8367D family devices, the routine checks:

- Chip ID must equal `0x6642` (decimal 26178).
- Chip revision must equal `0x0010` (decimal 16).

If both match, it binds the chip as `RTL8367D_CHIP_RTL8367D`.

### Cross-reference against upstream OpenWrt

Upstream OpenWrt's legacy target driver `target/linux/generic/files/drivers/net/
phy/rtl8367b.c` defines chip numbers in its own header:

```c
#define RTL8367B_CHIP_RTL8367S_VB   0x00106642
```

Packed as `(chip_ver << 16) | chip_num`, this matches the vendor detection values
byte-for-byte: `chip_ver = 0x0010`, `chip_num = 0x6642`. In OpenWrt's own naming
at that time, this chip was called `RTL8367S_VB`. The upstream `realtek,rtl8365mb`
DSA driver in modern kernels uses different family-based structure, which is what
this project's patch set addresses; see `KNOWN-ISSUES.md` §8.

## Reset sequence

`[VERIFIED]` The hardware reset sequence in `_5398` (offset `0x4090`) follows an
active-low reset:

| Step | Reset-line level | Delay |
|---|---|---|
| 1 | High, inactive | 500 ms |
| 2 | Low, asserted | 200 ms |
| 3 | High, deasserted | 200 ms |

A second, structurally similar path requests the GPIO under the
`rtl8367_gpio_reset` label, asserts it low, waits 200 ms and releases it.

A direct read of the live OEM device tree on this unit confirms
`/proc/device-tree/soc/ess-instance/ess-switch1@1/reset_gpio = 0x27`,
or GPIO39. GPIO33 is the 2.4 GHz LED. The current DTS uses GPIO39 with
`GPIO_ACTIVE_LOW`; see `HARDWARE.md`.

## SGMII / CPU port bring-up

`[SOURCE]` The vendor GPL source defines SGMII and HSGMII SerDes modes
and includes `MODE_EXT_HSGMII` / `PORT_SPEED_2500M` configuration for
the CPU trunk.

The GPL headers identify `RTL8367D_REG_SDS_MISC` (`0x1d11`) for
SerDes0/MAC6 and `RTL8367D_REG_SDS1_MISC0` (`0x1d78`) for SerDes1,
with mode constants `SGMII = 0x02` and `HSGMII = 0x12`.

The runtime and static observations:

- Stock hardware clock measurements show UNIPHY/GMAC TX and RX clocks
  at 312.5 MHz, consistent with a 2.5 Gbit/s SerDes rate.
- The OEM DTB contains `phy-mode = "sgmii"` on the GMAC side and
  `forced-speed = <0x9c4>` (2500), `forced-duplex = <1>` on the switch's
  `port@1`.
- The project's DTS uses `2500base-x`, fixed speed 2500 and `pause`
  on the GMAC and switch CPU-port fixed links.
- Physical OpenWrt boots (v0.2 through v0.4-3) report the switch and GMAC CPU
  link up at 2.5 Gbit/s full duplex with RX/TX flow control reported.

Together, the OEM runtime measurement and OpenWrt link logs support HSGMII 2.5G
operation. Subsequent testing on physical hardware confirmed external-port packet
forwarding: `br-lan` LAN1–4 forwarding was confirmed in v0.3, and WAN 1Gbps link
negotiation and router external ICMP ping were confirmed in v0.4-2 / v0.4-3.
Client LAN-to-WAN routing/NAT and sustained throughput under load remain to be tested;
see `TESTING.md` and `KNOWN-ISSUES.md` §4.

## Port mapping

`[SOURCE]` From the OEM rootfs's own `/etc/config/switch`:

| Logical port | Interface | Notes |
|---|---|---|
| 0 | WAN-side member | Appears alongside port 5 in the WAN VLAN |
| 1–4 | LAN1–LAN4 | Untagged per-VLAN |
| 5 | WAN | |
| 6 (tagged) | CPU (SoC) | Appears tagged in every LAN VLAN; this is the CPU trunk described above |

This is consistent with `HARDWARE.md`'s existing `LAN_PORTS`/`WAN_PORTS`/`CPU_PORTS`
table from `core_phy.sh`, with one clarification: `CPU_PORTS="16"` in that script is
a numbering artifact of a different (Broadcom) platform abstraction layer reused in
the vendor SDK's shell scripting and does not correspond to any port-number constant
used by the RTL8367D kernel driver itself, which addresses the CPU port as logical
port 6.

## procfs interface

`[SOURCE]` The module creates `/proc/driver/rtl8367s` and populates it with at
least `lut`, `mib`, and `vlan` entries (confirmed via strings present in the `.ko`
and the directory-creation/entry-registration call pattern in its init routine).
This interface is informational only (nothing in this port depends on it) and is
documented here for completeness.

## Caveats

- The GPL source tree used for cross-reference (`qca/src/u-boot-2016/drivers/net/
  rtl8367sc/`) is **not** a byte-for-byte match for the kernel module shipped in
  firmware 1.1.2; it is the closest available vendor source for the same chip
  family and was used to *identify* stripped functions by structural comparison,
  not assumed to be identical to the compiled binary. Every finding above states
  whether it was confirmed against the disassembly, the source, or both.
- While basic external-port forwarding (`br-lan` LAN-to-LAN in v0.3, WAN negotiation
  and external ICMP ping in v0.4-2/v0.4-3) has been verified on hardware, client
  LAN-to-WAN NAT forwarding, pause-frame exchange under heavy traffic, and maximum
  throughput have not yet been benchmarked.
- This analysis used firmware 1.1.2's `qca-ssdk.ko`. `KNOWN-ISSUES.md` §7 already
  established that the RTL8367-relevant code is byte-identical between the 1.0.1
  and 1.1.2 builds, so these findings are expected to apply equally to both.
