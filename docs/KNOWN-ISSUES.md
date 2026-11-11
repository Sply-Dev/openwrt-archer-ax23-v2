# Known issues, open questions, and licensing notes

Evidence tags used throughout this file, consistent with
[`archer-ax23-v2-port-status.md`](archer-ax23-v2-port-status.md):

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Checked by a command whose output is shown or linked. |
| `[SOURCE]` | Read directly from a file in this tree or a vendor-supplied archive. |
| `[OPEN]` | Unknown, or a hypothesis not yet tested. |

## 1. Switch chip identification (family D)

`[VERIFIED]` by static analysis, **not yet by physical unit**. The Ethernet switch
reports chip ID `0x6642`, chip revision `0x0010`, via the vendor `qca-ssdk` kernel
module's detection routine. Two independent lines of static analysis confirm this
maps to the Realtek RTL8367S-VB, "family D" in Realtek's own driver naming:

- Cross-reference against OpenWrt's legacy `rtl8367b.c` driver: `chip_num=0x6642`
  with `chip_ver=0x0010` matches that driver's own enum entry for
  `RTL8367B_CHIP_RTL8367S_VB` directly, a chip physically distinct from
  `chip_id=0x6367` (RTL8367RB-VB/RTL8367S, "family C").
- The `qca-ssdk.ko` detection routine's own internal structure: the disassembled
  function (`_5593`) contains two near-identical detection blocks, one per switch
  family, matching the vendor GPL source's `#if defined(CONFIG_DAL_RTL8367C)` /
  `#if defined(CONFIG_DAL_RTL8367D)` split. The family-C block is tested first and
  recognizes `0x0276`, `0x0597`, `0x6367`, none of which this device's firmware
  matches. Only the family-D block, recognizing `0x6642`, resolves. See
  `docs/RESEARCH.md` for the full derivation.

The register sequence read by `qca-ssdk.ko` (unlock write to `0x13C2`, chip ID from
`0x1300`, chip version from `0x1301`) also matches the upstream `rtl8365mb` driver's
own `RTL8365MB_MAGIC_REG`/`RTL8365MB_CHIP_ID_REG`/`RTL8365MB_CHIP_VER_REG` constants,
ruling out a register-offset mismatch as the source of the earlier `0x6642` vs
`0x6367` confusion.

This resolves a dispute raised during this port's public forum discussion, where the
"family C or D" question was initially reopened on the grounds that the chip's
commercial name (RTL8367SC, printed on this device by TP-Link) does not by itself
determine family, driver probe output does. The dual static-analysis result above
is that evidence, independent of the commercial part name.

**Hardware update (v0.2):** the OpenWrt driver reported an RTL8367S-VB switch and registered DSA ports. The supplied log does not show a numeric
chip-ID register read. Driver identification and port registration do not
establish reliable traffic through the external ports; see §4.

## 2. ath11k / Q6 calibration and board data

`[OPEN]` Wi-Fi compatibility was deliberately outside the v0.2 test scope;
board-data and full radio support were not configured for these tests. The
v0.2 kernel log shows ath11k probing the IPQ5018 and QCN6122 radios but failing
to fetch board data (including `failed to fetch board.bin` and a QMI board-file error of `-12`). The logs do not establish the cause of that failure or prove that
either radio is incompatible. ART offsets, calibration, association and traffic
remain unvalidated.

## 3. MAC address origin

`[OPEN]` The `tp_data` NAND partition is the leading candidate for the
LAN/WAN MAC address source, but the exact offset has not been confirmed on
this device. Patch `0002` adds the `02_network` LAN/WAN roles, without
board-specific MAC assignment. The v0.2 logs predate that patch.

## 4. Trunk link speed / SGMII vs HSGMII

The project's DTS configures the GMAC1 to switch CPU-port trunk as HSGMII
2.5G (`2500base-x`, fixed-link speed 2500) with `pause` on both fixed-link
nodes. The v0.2 OpenWrt kernel log reports the switch and GMAC links up at
2.5 Gbit/s, full duplex, with RX/TX flow control reported. That is a
hardware boot result for the CPU link, not evidence that all external ports
forward traffic reliably or that pause frames were exchanged.

Evidence from the OEM configuration is recorded separately:

- The U-Boot source configures `MODE_EXT_HSGMII` and `PORT_SPEED_2500M` and
  prints `Set RTL8367S SGMII 2.5Gbps`.
- On running stock hardware, UNIPHY/GMAC TX and RX clocks were measured at
  312.5 MHz, consistent with 2500Base-X rather than a 1 Gbit/s link.
- The OEM DTB contains `phy-mode = "sgmii"` on the GMAC side. The
  switch's `port@1` has `forced-speed = <0x9c4>` (2500) and
  `forced-duplex = <1>`. The `phy-mode` string alone does not establish
  a 1 Gbit/s operating speed.

The different naming used by the OEM DTB and the speed-related OEM properties
must be read together. The stock clock measurement supports the HSGMII 2.5G
interpretation; the OpenWrt v0.2 log independently reports a 2.5 Gbit/s
CPU link. Effective flow control, per-port carrier stability, packet
forwarding, VLAN operation and throughput remain to be tested. See
`DEVICE-TREE.md`, `RESEARCH.md` and `TESTING.md`.

## 5. LED polarity and physical port mapping

`[OPEN]` GPIO-to-LED mapping was recovered from the OEM U-Boot device tree blob
`[SOURCE]`, but polarity (active-high vs active-low) and the physical LAN1–4 port
label-to-silicon mapping have not been confirmed. A cable-swap test on hardware is
the planned verification method.

## 6. Upstream mainline acceptance

`[OPEN]` Upstream OpenWrt maintainers have previously indicated that 256MB-RAM
devices on the `ipq50xx` subtarget face a steep bar for mainline inclusion. The
practical path for this device is expected to be a community-maintained tree first,
with mainline submission considered later and separately, if at all.

## 7. GPL source completeness: `qca-ssdk` kernel module

`[VERIFIED]` Two versions of the vendor `qca-ssdk.ko` kernel module were extracted
from official TP-Link firmware images for this device:

| Firmware | `qca-ssdk.ko` SHA-256 | Size |
|---|---|---|
| 1.0.1 (Build 20241108 rel.47561) | `6751d953ca620fff740ce5bd4110c8582bf71ccc867d810f27145ceeeb30e143` | 1,326,116 bytes |
| 1.1.2 (Build 20250814 rel.14122) | `ae465c568e64099df1304183883c5c6e0b4da13eb357a6370819704a6bb70f96` | 1,330,052 bytes |

Both declare `license=Dual BSD/GPL` in their `.modinfo` ELF section, confirmed via:

```
readelf -p .modinfo qca-ssdk.ko
```

The vendor's own GPL source release for this device (`GPL_AX23v2.tar.gz`, downloadable
from TP-Link's GPL Code Center) includes build scaffolding for this module
(`Iplatform/openwrt/package/qca-ssdk/Makefile`) whose `local-development.mk` expects
the module's source at a fixed path relative to the SDK root:

```
LOCAL_SRC ?= $(TOPDIR)/qca/src/$(PKG_NAME)
```

i.e. `qca/src/qca-ssdk/`. This path layout matches the standard Qualcomm QSDK source
tree structure used across other vendors' IPQ-based GPL releases. In the TP-Link
`GPL_AX23v2.tar.gz` archive for this device, that directory does not exist, the
`qca/src/` tree contains only `linux-4.4`, `lk-af`, and `u-boot-2016`:

```
$ tar -tzf GPL_AX23v2.tar.gz | grep -i ssdk
./Iplatform/openwrt/package/qca-ssdk-shell/
./Iplatform/openwrt/package/qca-ssdk-shell/Makefile
./Iplatform/openwrt/package/qca-ssdk/
./Iplatform/openwrt/package/qca-ssdk/Makefile
./QCASPF11_4/ilq-11-4_cs_qca/qca/src/linux-4.4/arch/arm/boot/dts/exynos5440-ssdk5440.dts
```

Separately, the device's own build configuration (`product_configs/ax23v2/sdk.config`)
shows the module as actively selected for this product's build:

```
CONFIG_FEED_ssdk=y
CONFIG_PACKAGE_kmod-qca-ssdk-nohnat=y
CONFIG_PACKAGE_qca-ssdk-shell=y
```

**What this is, and isn't:** `Dual BSD/GPL` permits redistribution under the BSD
terms, which do not carry a source-disclosure obligation, so this is not presented
as a GPL violation claim. It is a factual, independently reproducible observation:
the vendor's own build system expects a source directory for this module that is
absent from the vendor's own published GPL archive for this device. Anyone can verify
this by downloading `GPL_AX23v2.tar.gz` from TP-Link's GPL Code Center and checking
the same path.

**Why this repository does not include the `.ko` binary itself:** the file originates
from the OEM firmware image, not from this project's own work, and its full
provenance (which parts are Qualcomm's SSDK vs. TP-Link's own RTL8367 integration)
isn't established. The hashes, paths, and firmware versions above are sufficient for
anyone to reproduce the exact same file from TP-Link's own public firmware downloads.

TP-Link's own GPL notice states: *"if you think TP-LINK need to provide any additional
source code files under GNU General Public License (GPL), please contact us at
support@tp-link.com. TP-LINK is committed to meeting the requirements of the GNU
General Public License (GPL) and will make all required source code available."*
This issue has not yet been raised with TP-Link through that channel.

### Diff between the two known `.ko` versions

`[VERIFIED]` Comparing the 1.0.1 and 1.1.2 versions of `qca-ssdk.ko` (same device,
different firmware releases) shows **no changes to RTL8367 switch support code**,
every RTL8367-related symbol and string (`rtl8367_proc_reg_rw`, `rtl8367_proc_mib_set`,
`rtl8367_gpio_reset`, etc.) is byte-identical between versions. The ~3.9KB size
difference is fully accounted for by added support for Realtek RTL8221/RTL8226 PHYs
(EEE, Giga-Lite, RTCT cable test) unrelated to this device's switch, plus the updated
build timestamp. This is useful context for anyone comparing behavior across firmware
versions: the switch-relevant code path has been stable across at least these two
releases.

## 8. Switch driver patch set used in this project (PR #19644)

`[VERIFIED]`. The eight `777-0x` patches previously carried in this tree
(an early v1 revision) were replaced by Mieczyslaw Nalewaj's 10-patch
series, `777-01` through `777-10`. The patch files currently carry v7
headers. For this project's build and test history, pre-v7 and v7
refer to the same series; they are not two separately validated
implementations. v9 and v10 have not been incorporated or tested here.

What changed from v1:

- `777-01` is now a dt-bindings entry for RTL8367S-VB rather than
  detection code; detection logic moved into `777-02`
  (`add-chip-family-infrastructure`, new in pre-v7).
- `777-03` through `777-08` carry real logic changes, not just
  renumbering. For example, `777-04` (RGMII mode for family D) in v1
  set the MAC7/EXT1 mux unconditionally; pre-v7 reads the register first
  and only sets the mux if MAC4/EXT1 is not already claiming the same
  pin, avoiding a real conflict between two MAC ports.
- `777-09` (L2/LUT access for family D) and `777-10` (RTL8367S-VB
  support in `rtl8365mb_main.c`/`Kconfig`) are new, not present in v1.

Verified before merging into this tree, in an isolated build container:

- All 10 patches apply cleanly against this project's kernel 6.18.55
  source (tested by reverting v1 and applying pre-v7 in sequence, via both
  `git apply` and `patch -p1`).
- The kernel compiles cleanly with the new patches
  (`make target/linux/compile`), no errors and no driver-specific
  warnings.
- The family-D exclusion gate in the separate SerDes-conduit patch
  (upstream `797`, formerly `778`) is unchanged in pre-v7:
  `rtl8365mb_sds_defer_needed()` still returns `false` for
  `RTL8365MB_FAMILY_D`, confirming that patch remains correctly not
  applicable to this device. See §10 for the pause-path analysis.

Third-party hardware validation for the upstream series (not this
specific device, but the same chip ID and family) remains the
`gusfm` report on a TP-Link EX511 v2 (RTL8367S-VB, chip ID `0x6642`,
family D): successful switch detection, a stable 1Gbps SGMII CPU link
up in 4.6s, 0 FCS/CRC/drop errors, working VLAN-aware bridging, 20
rounds of VLAN churn without loss, two clean reboot cycles.

**AX23 v2 validation:** the v0.2 initramfs booted on physical hardware;
the OpenWrt driver reported RTL8367S-VB detection and a 2.5 Gbit/s CPU
link. This does not establish reliable external-port forwarding, VLAN
behavior or v0.3 results. The exact source and patch revision of the
v0.2 image should accompany any attribution of a runtime result to a
particular patch.

## 8.1. A separate, already-merged series covers the same SerDes path (Johan Alvarado, net-next)

`[VERIFIED]`, added 2026-10-31. An earlier read of this series (see the old text of
§10, superseded below) treated it as a parallel, independently-developed line of
work, unconnected to PR #19644. Reviewing the full review thread shows that
framing was wrong: it is not a separate line, it is a **competing implementation
of the same SGMII/HSGMII SerDes bring-up that PR #19644 also touches, reviewed in
the same venue by the same people**, and it has already been merged.

- **Series:** `net: dsa: realtek: rtl8365mb: add SGMII/HSGMII support for
  RTL8367S`, Johan Alvarado, 2 patches, `net-next` v1 through v6.
- **Merged** into `netdev/net-next.git` on 2026-07-22 by Jakub Kicinski:
  - `net: dsa: realtek: rtl8365mb: add SGMII support for RTL8367S`:
    `git.kernel.org/netdev/net-next/c/0b577e2fe06c`
  - `net: dsa: realtek: rtl8365mb: add HSGMII support for RTL8367S`:
    `git.kernel.org/netdev/net-next/c/987137345f33`
- **`Reviewed-by`:** Maxime Chevallier, **Mieczyslaw Nalewaj** (the author of the
  pre-v7 series in §8), and **Luiz Angelo Daros de Luca**. `Tested-by:` Stanislaw Pal,
  on a TP-Link **Archer AX55 v1** (IPQ5018 + RTL8367S, HSGMII/2500base-x CPU
  trunk), the same SoC/switch combination as this device, though not this exact
  SKU or port configuration.
- **Chip coverage:** confirmed family D. Luiz Angelo's review states explicitly
  that "the only model that could use (H)SGMII in a different interface is
  RTL8370MB", i.e. for RTL8367S/RTL8367SB (this device's chip), the series'
  assumptions about which port the SerDes is muxed to hold.
- **Design, relevant to §10's pause gap:** models the SerDes as a real
  `phylink_pcs` (`mac_select_pcs`/`pcs_config`/`pcs_get_state`/`pcs_link_up`),
  keeps the embedded DW8051 microcontroller held in reset rather than loading
  vendor firmware into it (avoiding a firmware-blob dependency entirely), and
  programs the SerDes pause enables (`SDS_MISC_SGMII_TXFC_MASK`/`..._RXFC_MASK`)
  from the resolved pause state in `mac_link_up()`. This is a from-scratch
  pause implementation for the SerDes path, not a family-D-specific branch
  added to the `777-0x` code in this tree.

**Relationship to PR #19644 (§8):** not established with certainty, but the
review thread gives a strong signal: Mieczyslaw Nalewaj, author of the pre-v7
series this tree carries, reviewed and approved Alvarado's series rather than
objecting to a competing implementation. The more likely reading is that
#19644's SerDes/PCS portions will need to be rebased on top of the
infrastructure this series introduces, not the other way around, but this is
an inference from the review thread, not a statement from either author about
plans, and should be treated as `[OPEN]` until #19644 itself is updated or
commented on post-merge.

**Relevant but unrelated finding from the same thread (hardware note, not a
driver issue):** a long sub-thread documents a cold-boot trunk failure
reported during review, tested on an Archer AX55 v1 (IPQ5018, same SoC family
as this device). After extensive isolation (register dumps, selective resets,
a controlled delay experiment), the cause was identified as **a failing power
supply**, not the driver or this patch series, confirmed by an A/B/A swap
(old PSU → bad, new PSU → clean twice, old PSU again → bad again). Noted here
only so that a similar symptom during this project's own hardware bring-up
(`TESTING.md` H1-H4) is checked against PSU/power quality before being treated
as a driver or SerDes bug.

**Not yet done:** this tree still carries the `777-0x` (pre-v7, §8) implementation,
not Alvarado's. See §8.2 for what a direct comparison of scope shows, and what
upstream itself says about the gap between the two.

## 8.2. PR #19644's own checklist confirms the gap, and work to close it is already underway upstream

`[VERIFIED]`, added 2026-10-31. Two follow-up findings, read directly from
PR #19644's own description and comment thread on GitHub.

**Scope comparison: the `777-0x` patches and Alvarado's series do not overlap
as much as §8.1 might suggest.** Alvarado's series only replaces the SerDes/PCS
bring-up (what `777-07`/`777-08` do). It does not touch chip detection
(`777-01`, `777-02`, `777-10`), family D speed setting (`777-03`), RGMII mode
for family D (`777-04`), VLAN 4k (`777-05`), raw-VID PVID (`777-06`), or L2/LUT
access (`777-09`); none of this is in scope for, or mentioned anywhere in, the
Alvarado thread. Adopting Alvarado's series is therefore not a drop-in
replacement for this tree's `777-0x` patch set; it would mean keeping the
family D-specific patches for everything except SerDes/PCS, and rebasing
`777-07`/`777-08` on top of the `phylink_pcs` model Alvarado's series
introduces.

**PR #19644's own checklist says this directly.** The PR description lists:

- ~~fix mode mask calculation~~: already implemented
- ~~add VLAN and Bridging support to Realtek rtl8365mb DSA switch~~: already implemented
- ~~add SGMII and HSGMII mode support~~: already implemented
- ~~add support for rtl8367sb~~: already implemented
- **add support for rtl8367s-vb**: not checked off

The third and fourth items are exactly what §8.1 and the `0x6367`/RTL8367SB
patch found there cover; both are chip-ID `0x6367` (family C), already
upstream. The remaining, unchecked item, "rtl8367s-vb", is this device's own
chip (`0x6642`, family D, confirmed in §1). PR #19644's maintainer is tracking
the same gap this document identifies, in the same terms.

**This rebase work is already in progress upstream, not merely proposed.**
Comments on the PR (Mieczyslaw Nalewaj and `kuncy7`, Oct 2026) describe an
active, ongoing split:

- A separate PR, #25153 ("family C fix"), carries a SerDes conduit fix
  (`797`, already confirmed in §8 as not applicable to family D) that is being
  aligned line-for-line with this PR's own `931` patch
  (`net-dsa-realtek-rtl8365mb-defer-SerDes-bring-up-until-conduit-up`,
  renamed/renumbered from the `778`/`797` lineage this tree already tracks in
  §8).
- Once #25153 lands, `931`/this PR is expected to shrink to just the family D
  early-return in `rtl8365mb_sds_defer_needed()`, i.e. exactly the gate this
  tree's own §8 already confirmed is unchanged and correct for family D.
- `930-07`/`930-08` (the family D SerDes/PCS patches, this tree's `777-07`/
  `777-08` lineage) are explicitly flagged by Nalewaj as needing a rebase onto
  `797`/the new `phylink_pcs` infrastructure once the split above lands.
- Nalewaj has stated he has no RTL8367S-VB hardware and is developing "blind";
  he is explicitly looking for someone to submit the non-`931` commits
  upstream and to test RGMII mode on real RTL8367S-VB hardware, a possible
  opening for this project once physical hardware access exists (`TESTING.md`
  H0).

**Second, independent cold-boot finding (hardware note, not this series'
fault):** a different cold-boot trunk failure than the one in §8.1 is
documented by `kuncy7` on the same sibling board (Archer AX55 v1, IPQ5018).
Symptom: the SerDes reports link up, but every frame sent by the CPU arrives
at the switch's CPU port with a bad FCS and is dropped, diagnosable via
`ethtool -S eth0 | grep p06`: a climbing `dot3StatsFCSErrors` counter with
`ifInUcastPkts` stuck at 0 on a bad boot, both flat/moving normally on a good
one. `kuncy7` states explicitly this is unrelated to the family D patches.
This is a different signature from §8.1's PSU-related failure (which showed
drop events with zero FCS errors), noted here as a second, distinct
diagnostic to check against during this project's own hardware bring-up
(`TESTING.md` H1-H4) before attributing a dead trunk to a driver bug.

**Project implication for the open decision (§8.1):** adopting Alvarado's
SerDes/PCS model is not an immediate drop-in swap for `777-07`/`777-08` today,
but it is the direction upstream is already moving, with the exact rebase this
project would need already being discussed by the patch authors themselves.
The practical options are to wait for that upstream rebase to land and then
re-sync this tree's family D SerDes patches against it, or to attempt the
`777-07`/`777-08` → `phylink_pcs` rebase independently and offer it upstream -
which would directly address Nalewaj's stated need for someone to carry this
forward. Neither has been started; this remains `[OPEN]`.

## 8.3. Direct comparison: this tree's `777-07`/`777-08` already implement Alvarado's `phylink_pcs` model for family D

`[VERIFIED]`, added 2026-11-01, updated 2026-11-01. §8.2 above describes the
gap as seen from PR #19644's own checklist and comment thread (`930-07`/
`930-08` flagged by Nalewaj as needing a rebase onto the Alvarado/`797`
infrastructure, as of that thread). This section is a direct source
comparison, done independently of that thread, between Alvarado's merged
series and the `777-07`/`777-08` patches this tree actually carries (pre-v7,
the patch headers discussed in §10).

**Scope of this comparison:** Alvarado's series has two patches (SGMII base,
then HSGMII). Both have now been read and compared in full. The second
(HSGMII) turned out to be a small extension of the first, not a separate
mechanism: it adds a second SerDes tuning table (`rtl8365mb_sds_jam_hsgmii`),
switches `MAC8_SEL_SGMII_MASK` for `MAC8_SEL_HSGMII_MASK` in the same
`SDS_MISC_REG` touched by the first patch, generalizes
`rtl8365mb_interface_is_serdes()` to also accept
`PHY_INTERFACE_MODE_2500BASEX`, and treats `SPEED_2500` the same as
`SPEED_1000` in the force-mode speed field (that register has no 2.5G value;
the actual rate comes from the SerDes's own HSGMII configuration).
The AX23 v2 is configured and was tested with an HSGMII 2.5G CPU link (§4),
so the HSGMII portion is relevant. This source comparison is not a functional
validation of external-port traffic.

**Finding:** the structure is the same core model, not a divergent
implementation that still needs porting:

- Same SerDes registers, same names and addresses, in both: `SDS_INDACS_*`,
  `SDS_MISC_REG`, `SDS_REG_BMCR`, `SDS_REG_NWAY`, `SDS_REG_RESET`,
  `SDS_REG_LINK_STATUS`.
- Same approach to the embedded DW8051 microcontroller: held in reset rather
  than loaded with vendor firmware.
- Same two-phase BMCR reset sequence for the datapath.
- Same use of `phylink_pcs` (`pcs_config()`/`pcs_get_state()`/`pcs_link_up()`)
  as the bring-up model, rather than the vendor's own ad-hoc `mac_config()`
  path.

**The actual difference found is family coverage, not architecture:**
Alvarado's series uses `rtl8365mb_sds_write(priv, addr, data)` (no index
parameter) because it only targets family C, where the SerDes is accessed at
a single fixed location. `777-07` in this tree already generalizes this to
`rtl8365mb_sds_write(priv, index, addr, data)`, specifically to address
`RTL8365MB_D_SDS_EXT0_INDEX = 13`, family D's own SerDes index. Alvarado's
series has no re-latch logic at all, because that is specifically a family D
problem; `777-08` in this tree is exactly that re-latch work, and has no
equivalent in Alvarado's series because family C does not need it (family C's
version of the same cold-boot problem is instead what PR #25153/`797`
addresses, per §8 and §8.1).

**Conclusion:** `777-07`/`777-08`, as carried in this tree today, are not an
old `mac_config`-era implementation waiting to be rebased onto Alvarado's
`phylink_pcs` model. They already are a `phylink_pcs` implementation,
extended by `namiltd` specifically to cover family D's indexed SerDes access
and its re-latch requirement, concepts that do not exist in Alvarado's
family-C-only series. For this device, there is no pending port of the
Alvarado model into this tree's patches, that adaptation is already present.

**How this relates to §8.2's gap:** §8.2 is still accurate for what it
describes, the PR #19644 thread's own tracking of `930-07`/`930-08` against
the `797` split, and Nalewaj's stated lack of family D hardware. That gap is
about aligning the *upstream PR's* patch numbering and dependencies once
PR #25153 lands, not about this tree's `777-07`/`777-08` lacking the
architecture itself. The practical takeaway for this project is unchanged
from §8.2's bottom line: there is nothing to rebase in this tree's own copy
of the family D SerDes patches right now, the remaining work is to keep
tracking the upstream PRs (#19644, #25101, #25153) as they consolidate, and
to resync if a future revision changes the family D logic itself (not just
renames or splits it).

This is static source comparison, not a hardware result, consistent with the
rest of this document's SerDes/pause findings, see §4 and §10.

## 9. Boot slot selection mechanism

`[SOURCE]`, resolved, documented here because an earlier version of this tree's DTS
and documentation assumed the wrong mechanism. Boot slot (A/B) selection on this
device is handled through the U-Boot environment variable `tp_boot_idx`, set via
`fw_setenv tp_boot_idx <0|1>`, not by writing to the `BOOTCONFIG`/`BOOTCONFIG1` NAND
partitions. This is confirmed from three independent places in the vendor's own GPL
source and from a literal string match inside the `nvrammanager` binary itself; see
`HARDWARE.md`'s NAND partition layout section for the specific sources. The DTS in
this tree now marks `BOOTCONFIG`/`BOOTCONFIG1` read-only accordingly. This has a
direct effect on §3 and on `platform.sh`/sysupgrade design: the correct persistent
install path is writing the inactive `rootfs`/`rootfs_1` slot and then calling
`fw_setenv tp_boot_idx`, mirroring the pattern already used by `kuncy7`'s
`platform.sh` case for the sibling `tplink,archer-ax55-v1` board. Not yet implemented
in this tree, see `TESTING.md` H10.

## 10. `pause` on the GMAC1/CPU-port fixed-link

**Status:** `[VERIFIED]` by source inspection across three sources, the
mainline driver, this tree's `777-07`/`777-08` (v7), and their call sites.
**The v0.2 log reports RX/TX flow control on the 2.5 Gbit/s CPU link, but actual pause-frame exchange has not been measured.**

> **Correction (2026-11-01):** an earlier analysis concluded that pause was
> inert for family D. Inspection of the pre-v7/v7 series carried here found
> a pre-existing, family-agnostic forced-mode path. The previous analysis
> overlooked that path; no functional difference between pre-v7 and v7
> explains the correction.

### Background

The device tree sets `pause;` on the `fixed-link` nodes of both `&gmac1` and
`port@6` (CPU port), intending to enable flow control on the trunk.
Third-party reports (AX5x boards, forum) measured ~13% UDP loss without it.

### Driver path for pause

Read directly from the mainline driver
(`drivers/net/dsa/realtek/rtl8365mb_main.c`, upstream `torvalds/linux`, no
family D patches applied; this function predates the entire `777-0x`
series).

`rtl8365mb_phylink_mac_link_up()` calls, unconditionally for any RGMII or
SerDes interface:

```c
ret = rtl8365mb_ext_config_forcemode(priv, port, true, speed,
                                     duplex, tx_pause, rx_pause);
```

`rtl8365mb_ext_config_forcemode()` itself (mainline, lines ~1624–1697) writes
the resolved `tx_pause`/`rx_pause` straight into the
`RTL8365MB_DIGITAL_INTERFACE_FORCE_REG` pause bits, with **no family branch
of any kind**, this is generic forced-mode configuration that exists for
every chip this driver supports, including before family D was ever added.

### What the family D patches (`777-07`/`777-08`, v7) actually change

Neither patch touches `rtl8365mb_ext_config_forcemode()` or its call sites in
`mac_link_up()`/`mac_link_down()`, confirmed by:

```bash
grep -rn "ext_config_forcemode" target/linux/generic/pending-6.18/777-*.patch
```

which only matches a comment in `777-07` and an unrelated context line in
`777-08`.

What they *do* change is the **family-C-only SerDes-level pause path**, a
second, redundant mechanism (`RTL8365MB_SDS_MISC_SGMII_TXFC_MASK`/
`..._RXFC_MASK`, written separately in `mac_link_up()` after
`ext_config_forcemode()` returns). `777-07` gates that second path off for
family D explicitly:

```c
if (rtl8365mb_interface_is_serdes(interface) &&
    rtl8365mb_get_family(priv) != RTL8365MB_FAMILY_D) {
        u32 val = 0;
        ...
```

with the comment:

> *"Family D does not use this path: its pause bits are set in the
> forced-mode register by `rtl8365mb_ext_config_forcemode()`."*

That comment is accurate and verifiable against the mainline function above
it is not describing a missing feature; it is documenting that family D
doesn't need the family-C-specific second path because the generic one
already covers it.

### Practical implication

The `pause;` property in the DTS is **not** inert by driver design. The code
path that honors it (`ext_config_forcemode()`, called from
`mac_link_up()`/`mac_link_down()` for any RGMII or SerDes port) is
family-agnostic and has been present in this driver since before family D
support existed. There is no family D-specific gap in the pause code path,
as earlier revisions of this section claimed.

### Still `[OPEN]`

The v0.2 log reports RX/TX flow control on the 2.5 Gbit/s CPU link. It
does not show actual pause frames, whether the link partner honors them,
or sustained traffic behavior on this chip. The driver path supports the
`pause;` property by source inspection; its on-wire effect remains unverified.

### Revision note

The inspected `777-07` and `777-08` files carry `[PATCH net-next v7]`
headers. The project also referred to this series as pre-v7 in earlier
documentation. These labels do not denote distinct project builds or
a change in the family D pause path. Neither v9 nor v10 has been
incorporated or tested in this project.
