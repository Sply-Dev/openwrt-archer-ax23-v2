# Research notes — vendor firmware and `qca-ssdk.ko` analysis

This document summarizes the reverse-engineering work that informed this port's
switch driver patches (`target/linux/generic/pending-6.18/777-01`–`777-08`) and
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

This port did not start from the device tree outward — it started from a full,
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
in the pipeline it sits* — not the specific key, IV, or other artifact-specific
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
the shipped `.ko` — one per switch family (RTL8367C-and-related first, RTL8367D
second) — matching the `#if defined(CONFIG_DAL_RTL8367C)` / `#if
defined(CONFIG_DAL_RTL8367D)` split in source. In the `.ko`, this is symbol `_5593`
at offset `0x43f0` (352 bytes); its caller, `hal_find_device` (`_2936` at `0x4550`),
dispatches to a per-chip control-structure table based on the detected type.

The detection sequence, identical in structure for both families and confirmed
byte-for-byte between source and disassembly:

1. Unlock: write `0x0249` to register `0x13C2`.
2. Read chip ID from register `0x1300`.
3. Read chip revision from register `0x1301`.
4. Lock: write `0x0000` to register `0x13C2`.
5. Compare the ID against a table of known values.

For the RTL8367D path specifically, only one ID is recognized:

| Chip ID | Family | Result |
|---|---|---|
| `0x6642` | RTL8367D | `CHIP_RTL8367D` (internal type `4`) |
| anything else | — | falls through, eventually `RT_ERR_CHIP_NOT_FOUND` |

This confirms `KNOWN-ISSUES.md` §1's existing `0x6642` finding with function-level
provenance. The disassembly also clarifies **where the `0x6367` value some earlier,
less precise notes associated with this device actually comes from**: `0x6367` is
one of three IDs (`0x0276`, `0x0597`, `0x6367`) recognized in the *separate*,
earlier RTL8367C-family detection block in the same function (`_5593`, instructions
at offsets `0x4458`–`0x4518`), which runs **before** the RTL8367D block and is
skipped via fallthrough once none of those three match. `0x6367` is therefore not
an alternate ID for this device's chip — it belongs to a different switch family
the same generic detection routine also tests for, and the AX23 v2's `qca-ssdk.ko`
only ever resolves to `0x6642`/RTL8367D for this hardware. This resolves the open
`0x6642` vs `0x6367` question `TESTING.md` referenced without fully explaining.

## MDIO/SMI register access protocol

`[VERIFIED]` Switch register access (both read and write) goes through an indirect,
4-step MDIO transaction addressed to a fixed PHY ID, implemented in GPL source as
`rtl8367d_smi_read`/`rtl8367d_smi_write` (`rtl8367d_smi.c`) and confirmed in the
`.ko` disassembly at symbols `_5398` (read, `0x94f8c`) and `_5399` (write,
`0x95030`).

**PHY ID:** `29` (`0x1D`), hardcoded in every call (`mov r1, #29`) in both
functions. Source marks this as compile-time selectable
(`CONFIG_RTL8367SC_PHYID_0` → PHY 0, else → PHY 29) via `#if`, but the shipped
binary only contains the PHY-29 path — no PHY-0 path exists in this `.ko`.

**Read sequence** (4 MDIO register writes/reads, all to PHY 29):

| Step | Register | Value | Meaning |
|---|---|---|---|
| 1 | 31 (`CTRL0`) | `0x000E` | Select address-command mode |
| 2 | 23 (`ADDRESS`) | target address | Set the switch register address to read |
| 3 | 21 (`CTRL1`) | `0x0001` | Trigger read operation |
| 4 | 25 (`DATA_READ`) | — | Read back the 16-bit result |

**Write sequence** (4 MDIO register writes, all to PHY 29):

| Step | Register | Value | Meaning |
|---|---|---|---|
| 1 | 31 (`CTRL0`) | `0x000E` | Select address-command mode |
| 2 | 23 (`ADDRESS`) | target address | Set the switch register address to write |
| 3 | 24 (`DATA_WRITE`) | data | Set the 16-bit value to write |
| 4 | 21 (`CTRL1`) | `0x0003` | Trigger write operation |

Both sequences are wrapped in a spinlock (`_raw_spin_lock_bh`/`_raw_spin_unlock_bh`
around the whole transaction).

A fifth register, `MDC_MDIO_START_REG` (29 — note this is a *register number*, not
the PHY ID, which is also 29; a naming coincidence in the vendor source, not a
reused value), is defined in source but never referenced in either the read or
write function, in source or in the disassembly. It is unused on this device.

**Transport layer:** `[VERIFIED]` The low-level MDIO transaction functions
(`_4193` for read at `0xab3ec`, `_4194` for write at `0xab444`) resolve a `struct
mii_bus` pointer and call through its `.read`/`.write` function-pointer slots
(offsets `+32` and `+36` respectively within the struct) — i.e. the Linux kernel's
standard `mdiobus_read`/`mdiobus_write` mechanism. **There is no GPIO bit-banging**
for MDIO on this device; access goes through the SoC's MDIO controller via the
normal kernel MII bus abstraction. This confirms the device tree's `mdio0` node
(see `DEVICE-TREE.md`) is the correct binding point and that no custom bit-bang GPIO
driver is needed.

## Switch reset sequence

`[VERIFIED]` Hardware reset of the switch is driven by GPIO 33 (matching the
GPIO map in `HARDWARE.md`, which already listed GPIO33 as shared between the
2.4GHz LED and switch reset), using the `gpiod_direction_output_raw` /
`gpiod_set_raw_value` kernel GPIO descriptor API — not raw register writes. The
sequence:

| Step | Action | Delay after |
|---|---|---|
| 1 | Set GPIO33 HIGH (idle/inactive) | 500 ms |
| 2 | Set GPIO33 LOW (assert reset) | 200 ms |
| 3 | Set GPIO33 HIGH (deassert reset) | 200 ms |

I.e. reset is **active-low**. A second, structurally similar reset path exists in
the module (requesting the GPIO under the label `"rtl8367_gpio_reset"`, asserting
low, waiting 200ms, then releasing) that appears to be a secondary/re-probe path
rather than the main init sequence; its exact trigger condition was not determined.

This is new, actionable information for `DEVICE-TREE.md`: the DTS's
`reset-gpios` property should specify `GPIO_ACTIVE_LOW` and, if the binding
supports it, the vendor's timing (500ms pre-assert settle, 200ms assert, 200ms
post-deassert settle) is a reasonable default to match known-working vendor
behavior, though the binding may not expose settle time directly.

## SGMII / CPU port bring-up

`[OPEN]`/`[SOURCE]`, actively disputed. The GPL source (`dal_rtl8367d_port.c`) shows
CPU-port SerDes configuration driven through register `RTL8367D_REG_SDS_MISC`
(`0x1d11`) for SerDes0/MAC6 and `RTL8367D_REG_SDS1_MISC0` (`0x1d78`) for SerDes1,
with mode constants including `SGMII = 0x02` and `HSGMII = 0x12`. This confirms both
modes exist as options in the vendor driver, it does not by itself establish which
one this device actually uses.

This finding is included with lower confidence than the sections above: it was
reported from GPL source reading during an earlier analysis pass in this project
that did not produce the same disassembly-level, instruction-by-instruction
cross-check applied to chip detection and MDIO above. The register numbers and
mode constants are taken directly from vendor header definitions (high confidence
for their existence), but the exact bit-field sequence of writes during bring-up
has not been independently re-verified against `.ko` disassembly in this pass.
Treat the register/constant names as reliable and the precise write ordering as
indicative, not confirmed.

**Update: the question of which mode this device actually uses is now a live
dispute, not an open-but-unexamined detail.** Three additional data points were
found after the analysis above:

- The OEM U-Boot source for this device (`ipq5018_gmac.c`) configures
  `MODE_EXT_HSGMII` with `PORT_SPEED_2500M` for the GMAC1 to switch link, i.e. the
  `HSGMII = 0x12` constant above, not `SGMII = 0x02`.
- The DTB extracted from this device's own stock firmware shows `phy-mode = "sgmii"`
  with a `fixed-link` speed of 1000, i.e. the `SGMII = 0x02` constant, contradicting
  the U-Boot source for the same device.
- Production OpenWrt DTS files for sibling TP-Link boards on the same switch
  platform (AX53 v2, AX58 v2, from `kuncy7/openwrt-nss-edma`) use `2500base-x` at a
  50MHz reference clock, matching the HSGMII reading, not the DTB reading.

This is an unresolved internal contradiction between two OEM sources for the same
device (U-Boot source code vs. extracted DTB), not a disagreement between this
project and a reference. It is possible the OEM runs the link below its negotiated
maximum in the stock DTB for reasons not evident from source alone. Resolving this
needs either a boot log showing the actual negotiated link speed on this device, or
a direct read of the UNIPHY/SerDes PCS mode registers (`RTL8367D_REG_SDS_MISC` /
`RTL8367D_REG_SDS1_MISC0` above) on a running unit. See `docs/HARDWARE.md` and
`docs/DEVICE-TREE.md` for how this currently affects the DTS, and
`docs/KNOWN-ISSUES.md` §4 for the tracked open question, including a related finding
that a `pause` property on the `fixed-link` node may be required regardless of which
speed is correct.

## Port mapping

`[SOURCE]` From the OEM rootfs's own `/etc/config/switch`:

| Logical port | Interface | Notes |
|---|---|---|
| 0 | WAN-side member | Appears alongside port 5 in the WAN VLAN |
| 1–4 | LAN1–LAN4 | Untagged per-VLAN |
| 5 | WAN | |
| 6 (tagged) | CPU (SoC) | Appears tagged in every LAN VLAN; this is the SGMII uplink described above |

This is consistent with `HARDWARE.md`'s existing `LAN_PORTS`/`WAN_PORTS`/`CPU_PORTS`
table from `core_phy.sh`, with one clarification: `CPU_PORTS="16"` in that script is
a numbering artifact of a different (Broadcom) platform abstraction layer reused in
the vendor SDK's shell scripting and does not correspond to any port-number constant
used by the RTL8367D kernel driver itself, which addresses the CPU port as logical
port 6. This does not change any existing documentation or DTS content — it is
noted here so the `"16"` value in `HARDWARE.md` isn't mistaken for a driver-level
port number if read in isolation.

## procfs interface

`[SOURCE]` The module creates `/proc/driver/rtl8367s` and populates it with at
least `lut`, `mib`, and `vlan` entries (confirmed via strings present in the `.ko`
and the directory-creation/entry-registration call pattern in its init routine);
a `reg_rw`-style entry for direct register access is plausible given the strings
present but its exact name was not independently confirmed byte-for-byte against
a `proc_create_data` call site in this pass. This interface is informational only
— nothing in this port depends on it — and is documented here for completeness
in case it's useful for future on-device debugging.

## Caveats

- The GPL source tree used for cross-reference (`qca/src/u-boot-2016/drivers/net/
  rtl8367sc/`) is **not** a byte-for-byte match for the kernel module shipped in
  firmware 1.1.2 — it is the closest available vendor source for the same chip
  family and was used to *identify* stripped functions by structural comparison,
  not assumed to be identical to the compiled binary. Every finding above states
  whether it was confirmed against the disassembly, the source, or both.
- All findings here concern **register-level protocol and detection logic only**.
  None of this constitutes evidence that Ethernet traffic actually passes over the
  SGMII link on physical hardware — see `KNOWN-ISSUES.md` §4, which remains open.
- This analysis used firmware 1.1.2's `qca-ssdk.ko`. `KNOWN-ISSUES.md` §7 already
  established that the RTL8367-relevant code is byte-identical between the 1.0.1
  and 1.1.2 builds, so these findings are expected to apply equally to both.
