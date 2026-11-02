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

**Still open:** none of this has been confirmed by reading the chip ID register on a
physical unit, or by observing the driver's own probe message (`"found an RTL8367S-VB
switch"` vs `"found an RTL8367S switch"`) in a real boot log. No conclusion about
functional hardware compatibility (as opposed to chip identification) should be drawn
until that happens, see §4 below and `TESTING.md` test H3.

## 2. ath11k / Q6 calibration and board data

`[OPEN]` Calibration data paths for both radios (IPQ5018 internal 2.4GHz, QCN6102
5GHz over PCIe) have been wired into the device tree and hotplug scripts based on
vendor board-data file locations `[SOURCE]`. Neither radio has been tested on
hardware. The QCN6122 firmware package built into test images showed only `m3_fw`
with no `board-2.bin`/`firmware-2.bin`; the implication of this is still open.

## 3. MAC address origin

`[OPEN]` The `tp_data` NAND partition is the leading candidate for the LAN/WAN MAC
address source (pattern seen in comparable devices using the same vendor SDK), but
the exact offset within that partition has not been confirmed on this device. Requires
a UART dump to resolve. Separately, no `02_network` case exists yet to actually
assign the extracted MAC(s) to the LAN/WAN interfaces, see §4's related gap on
install/boot integration.

## 4. Trunk link speed / SGMII vs HSGMII

`[VERIFIED by GPL source inspection, not hardware]`. MDIO-level detection of the
switch does not by itself demonstrate working Ethernet traffic over the GMAC1 to
switch CPU port link, so this is not a claim that Ethernet works. But the link
mode question itself is resolved: this port's DTS uses SGMII, fixed 1000Mbps.

This device has five 1G physical ports (WAN + LAN1-4); there is no port on this
SKU that exceeds 1G, so a 2.5G trunk would carry no traffic beyond what SGMII 1G
already provides.

Evidence for SGMII 1G:

- This matches the OEM device tree blob extracted from this unit's own stock
  firmware (`phy-mode sgmii`, `fixed-link speed 1000`). The DTB is what the
  kernel actually uses at runtime, as opposed to U-Boot's early bring-up.

Evidence previously cited for HSGMII 2.5G, and why it does not hold up:

- The OEM U-Boot source (`ipq5018_gmac.c`, `rtl8367_sw_init()`) does configure
  `MODE_EXT_HSGMII` / `PORT_SPEED_2500M`, forced, on `EXT_PORT0` and
  `EXT_PORT1`. But this routine runs unconditionally for any board built with
  `CONFIG_TP_EXT_SWITCH_RTL8367_ALL` and an RTL8367 switch present, gated only
  on switch presence, not board ID or port capability. It also configures two
  extension ports, not this device's single CPU trunk port. This matches
  generic Qualcomm/Realtek SDK bring-up code, not a deliberate per-board
  choice.
- The same function contains an HSGMII-specific signal fix
  (`rtl8367d_setAsicReg` sequence) that is commented out, with a note above it
  reading "According to rtk AE, these ops have been included in 1.4.2 driver"
  — i.e. TP-Link's own firmware engineers disabled this HSGMII workaround as
  obsolete.
- Production DTS files for sibling boards on the same switch platform (AX53 v2,
  AX58 v2, from `kuncy7/openwrt-nss-edma`) use `2500base-x` at 50MHz. But those
  boards have 2.5G physical ports, unlike this device's 1G ports; their trunk
  speed is explained by their own port hardware, not by anything specific to
  this device.

See 10 for a related finding: the `pause` property previously set on both
`fixed-link` nodes has been removed, since its only stated justification (a
2.5G CPU trunk unable to backpressure against 1G physical ports) does not
apply once the trunk itself is SGMII 1G.

Still UNVERIFIED on physical AX23 v2 hardware (no UART yet). This needs to be
tested (`TESTING.md` H3/H4) before any claim of "Ethernet works" is made. If
the trunk does not come up in SGMII 1G, HSGMII 2.5G + a 50MHz UNIPHY reference
(with `pause` restored) is the fallback to try. See `docs/DEVICE-TREE.md`'s
dedicated section and `docs/RESEARCH.md`'s SGMII/CPU port bring-up section.

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

## 7. GPL source completeness — `qca-ssdk` kernel module

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

## 8. Switch driver patch set updated to upstream pre-v7 (PR #19644)

`[VERIFIED]`. The eight `777-0x` patches previously carried in this tree
(an early v1 revision) have been replaced with the pre-v7 revision of
Mieczyslaw Nalewaj's (`namiltd`) switch driver series, from the
`namiltd/openwrt` branch `Realtek_DSA` (net-next pre-v7, `Reviewed-by:`
Linus Walleij and Luiz Angelo Daros de Luca). This tree now carries 10
patches, `777-01` through `777-10`.

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
  applicable to this device. See §10's "Next step" resolution below.

Third-party hardware validation for the upstream series (not this
specific device, but the same chip ID and family) remains the
`gusfm` report on a TP-Link EX511 v2 (RTL8367S-VB, chip ID `0x6642`,
family D): successful switch detection, a stable 1Gbps SGMII CPU link
up in 4.6s, 0 FCS/CRC/drop errors, working VLAN-aware bridging, 20
rounds of VLAN churn without loss, two clean reboot cycles.

**Still open:** this confirms the patch set builds, not that it works
on physical AX23 v2 hardware. No UART-based or boot-based functional
test has been run on this device with the pre-v7 patches. The PR itself
is still in draft upstream, requires 6 reviewer approvals to merge,
and had 1 failing check as of this writing.

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
  - `net: dsa: realtek: rtl8365mb: add SGMII support for RTL8367S` -
    `git.kernel.org/netdev/net-next/c/0b577e2fe06c`
  - `net: dsa: realtek: rtl8365mb: add HSGMII support for RTL8367S` -
    `git.kernel.org/netdev/net-next/c/987137345f33`
- **`Reviewed-by`:** Maxime Chevallier, **Mieczyslaw Nalewaj** (the author of the
  pre-v7 series in §8), and **Luiz Angelo Daros de Luca**. `Tested-by:` Stanislaw Pal,
  on a TP-Link **Archer AX55 v1** (IPQ5018 + RTL8367S, HSGMII/2500base-x CPU
  trunk) - the same SoC/switch combination as this device, though not this exact
  SKU or port configuration.
- **Chip coverage:** confirmed family D. Luiz Angelo's review states explicitly
  that "the only model that could use (H)SGMII in a different interface is
  RTL8370MB" - i.e. for RTL8367S/RTL8367SB (this device's chip), the series'
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
infrastructure this series introduces, not the other way around - but this is
an inference from the review thread, not a statement from either author about
plans, and should be treated as `[OPEN]` until #19644 itself is updated or
commented on post-merge.

**Relevant but unrelated finding from the same thread (hardware note, not a
driver issue):** a long sub-thread documents a cold-boot trunk failure
reported during review, tested on an Archer AX55 v1 (IPQ5018, same SoC family
as this device). After extensive isolation (register dumps, selective resets,
a controlled delay experiment), the cause was identified as **a failing power
supply**, not the driver or this patch series - confirmed by an A/B/A swap
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
access (`777-09`) - none of this is in scope for, or mentioned anywhere in, the
Alvarado thread. Adopting Alvarado's series is therefore not a drop-in
replacement for this tree's `777-0x` patch set; it would mean keeping the
family D-specific patches for everything except SerDes/PCS, and rebasing
`777-07`/`777-08` on top of the `phylink_pcs` model Alvarado's series
introduces.

**PR #19644's own checklist says this directly.** The PR description lists:

- ~~fix mode mask calculation~~ - already implemented
- ~~add VLAN and Bridging support to Realtek rtl8365mb DSA switch~~ - already implemented
- ~~add SGMII and HSGMII mode support~~ - already implemented
- ~~add support for rtl8367sb~~ - already implemented
- **add support for rtl8367s-vb** - not checked off

The third and fourth items are exactly what §8.1 and the `0x6367`/RTL8367SB
patch found there cover - both are chip-ID `0x6367` (family C), already
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
  early-return in `rtl8365mb_sds_defer_needed()` - i.e. exactly the gate this
  tree's own §8 already confirmed is unchanged and correct for family D.
- `930-07`/`930-08` (the family D SerDes/PCS patches - this tree's `777-07`/
  `777-08` lineage) are explicitly flagged by Nalewaj as needing a rebase onto
  `797`/the new `phylink_pcs` infrastructure once the split above lands.
- Nalewaj has stated he has no RTL8367S-VB hardware and is developing "blind";
  he is explicitly looking for someone to submit the non-`931` commits
  upstream and to test RGMII mode on real RTL8367S-VB hardware - a possible
  opening for this project once physical hardware access exists (`TESTING.md`
  H0).

**Second, independent cold-boot finding (hardware note, not this series'
fault):** a different cold-boot trunk failure than the one in §8.1 is
documented by `kuncy7` on the same sibling board (Archer AX55 v1, IPQ5018).
Symptom: the SerDes reports link up, but every frame sent by the CPU arrives
at the switch's CPU port with a bad FCS and is dropped - diagnosable via
`ethtool -S eth0 | grep p06`: a climbing `dot3StatsFCSErrors` counter with
`ifInUcastPkts` stuck at 0 on a bad boot, both flat/moving normally on a good
one. `kuncy7` states explicitly this is unrelated to the family D patches.
This is a different signature from §8.1's PSU-related failure (which showed
drop events with zero FCS errors) - noted here as a second, distinct
diagnostic to check against during this project's own hardware bring-up
(`TESTING.md` H1-H4) before attributing a dead trunk to a driver bug.

**Bottom line for this project's open decision (§8.1):** adopting Alvarado's
SerDes/PCS model is not an immediate drop-in swap for `777-07`/`777-08` today,
but it is the direction upstream is already moving, with the exact rebase this
project would need already being discussed by the patch authors themselves.
The practical options are to wait for that upstream rebase to land and then
re-sync this tree's family D SerDes patches against it, or to attempt the
`777-07`/`777-08` → `phylink_pcs` rebase independently and offer it upstream -
which would directly address Nalewaj's stated need for someone to carry this
forward. Neither has been started; this remains `[OPEN]`.

## 8.3. Direct comparison: this tree's `777-07`/`777-08` already implement Alvarado's `phylink_pcs` model for family D

`[VERIFIED, partial]`, added 2026-11-01. §8.2 above describes the gap as seen
from PR #19644's own checklist and comment thread (`930-07`/`930-08` flagged
by Nalewaj as needing a rebase onto the Alvarado/`797` infrastructure, as of
that thread). This section is a direct source comparison, done independently
of that thread, between Alvarado's merged series and the `777-07`/`777-08`
patches this tree actually carries (pre-v7, hashes in §10's revision table).

**Scope of this comparison:** Alvarado's series has two patches (SGMII base,
then HSGMII). Only the first (SGMII base) was read and compared in full; the
second was not pulled, since the SerDes register layer it extends is
structurally identical to the first and did not appear to change the
conclusion below. This section should be treated as resting on that first
patch only, until the second is reviewed.

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

**Still `[OPEN]`:** Alvarado's second patch (HSGMII) has not been reviewed
against this tree. All of the above is static source comparison, not a
hardware result, consistent with the rest of this document's SerDes/pause
findings, see §4 and §10.

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

**Status:** `[VERIFIED]` by source inspection across three sources — the
mainline driver, this tree's `777-07`/`777-08` (v7), and their call sites.
**Not yet confirmed on physical hardware.**

> **Correction (2026-11-01):** this section previously concluded pause is
> inert for family D. That conclusion was based on an earlier (pre-v7)
> revision of the `777-0x` patches no longer carried in this tree.
> Re-reading the v7 patches currently in `target/linux/generic/pending-6.18/`
> shows the opposite: pause for family D goes through a pre-existing,
> family-agnostic code path that both v1 and the earlier reading of this
> section missed.

### Background

The device tree sets `pause;` on the `fixed-link` nodes of both `&gmac1` and
`port@6` (CPU port), intending to enable flow control on the trunk.
Third-party reports (AX5x boards, forum) measured ~13% UDP loss without it.

### How pause actually reaches the wire

Read directly from the mainline driver
(`drivers/net/dsa/realtek/rtl8365mb_main.c`, upstream `torvalds/linux`, no
family D patches applied — this function predates the entire `777-0x`
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
of any kind** — this is generic forced-mode configuration that exists for
every chip this driver supports, including before family D was ever added.

### What the family D patches (`777-07`/`777-08`, v7) actually change

Neither patch touches `rtl8365mb_ext_config_forcemode()` or its call sites in
`mac_link_up()`/`mac_link_down()` — confirmed by:

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
— it is not describing a missing feature, it is documenting that family D
doesn't need the family-C-specific second path because the generic one
already covers it.

### Practical implication, revised

The `pause;` property in the DTS is **not** inert by driver design. The code
path that honors it (`ext_config_forcemode()`, called from
`mac_link_up()`/`mac_link_down()` for any RGMII or SerDes port) is
family-agnostic and has been present in this driver since before family D
support existed. There is no family D-specific gap in the pause code path,
as earlier revisions of this section claimed.

### Still `[OPEN]`

This is static analysis, not a hardware result. Nothing here confirms:

- that the far-end link partner honors the pause frames this device would emit,
- that the register write has the intended effect in practice on this specific chip revision,
- or that there isn't some runtime interaction (timing, SerDes re-latch state from `777-08`, etc.) that prevents the forced pause bits from taking effect on a real family D part.

This requires a physical unit and UART access to verify (`TESTING.md`,
blocked on UART per project status). Until then, `pause;` should be read as
**"implemented in the driver path this tree carries, unverified on
hardware"** — not "unimplemented."

### Revision note

This correction was found by comparing the pre-v7 patch text this section
originally cited against the v7 patches actually present in this tree:

| Patch | Hash | Label |
|---|---|---|
| `777-07` | `9af9ff10b3f4b49f1a17859022e8cb1ff25f8ae8` | `[PATCH net-next v7 07/10]` |
| `777-08` | `6d6d9120b8851faa3e33bd48d59340881a75c985` | `[PATCH net-next v7 08/10]` |

then confirmed against mainline.

An earlier draft of this correction, based on PR #25101's `v6` revision
(hash `a1eb1a7a988b8deefb8828f498b98af5c5fc9bbd` for `777-07`), was caught as
the wrong revision before being written here — v6 and v7 are functionally
identical for this specific finding. The only v6→v7 diff is unrelated: a
`cpu_dp->index` filter added to `rtl8365mb_conduit_state_change()` in
`777-08`, plus a `Reviewed-by` tag. The hash mismatch is noted so a future
check against a v8+ revision knows exactly which commit this correction was
verified against.
