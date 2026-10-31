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

`[OPEN]`, actively disputed. MDIO-level detection of the switch does not by itself
demonstrate working Ethernet traffic over the GMAC1 to switch CPU port link. Beyond
that general caveat, the specific link mode is now in question:

- This port's DTS configures SGMII, fixed 1000Mbps, matching the OEM device tree
  blob extracted from this unit's own stock firmware.
- The OEM U-Boot source (`ipq5018_gmac.c`) configures `MODE_EXT_HSGMII` /
  `PORT_SPEED_2500M` for the same link, contradicting the OEM DTB.
- Production DTS files for sibling boards on the same switch platform (AX53 v2,
  AX58 v2, from `kuncy7/openwrt-nss-edma`) use `2500base-x` at 50MHz, not SGMII at
  25MHz.
- A `pause` property on the `fixed-link` node was reported by `kuncy7` as necessary
  on related hardware to avoid measured UDP loss (~13% in a third-party test) when
  the switch cannot backpressure a 2.5G GMAC against 1G physical ports. This port's
  DTS does not currently have `pause` set.

None of this is resolved on physical AX23 v2 hardware. This needs to be tested
(`TESTING.md` H3/H4) before any claim of "Ethernet works" is made, and before
deciding whether the DTS should move to HSGMII 2.5G. See `docs/DEVICE-TREE.md`'s
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

## 8. Switch driver patch set is an outdated revision (v1 vs upstream v5/v6)

`[SOURCE]`/`[OPEN]`. The eight `777-0x` patches carried in this tree
(`target/linux/generic/pending-6.18/777-01` through `777-08`) are an early revision
of a switch driver series by Mieczyslaw Nalewaj (`namiltd`) that has since progressed
substantially further in draft upstream PR `openwrt/openwrt#19644` (branch
`Realtek_DSA`), now at v5/v6:

- The upstream series has 11 patches (`777-01` through `777-10`, plus `797`), this
  tree has 8 (`777-01` through `777-08`). The two additional family-D patches not in
  this tree are `777-09` (L2/LUT support) and `797` (SerDes conduit re-latch,
  originally numbered `778`, authorship adjusted to credit `kuncy7` during upstream
  review).
- This is not purely a version bump. A content diff of `777-04` (RGMII mode for
  family D) between this tree's v1 and the upstream v5/v6 shows a logic change, not
  just a cosmetic one: v1 sets the MAC7/EXT1 mux unconditionally, v5/v6 reads the
  register first and only sets the mux if MAC4/EXT1 is not already claiming the same
  pin, avoiding a real conflict between two MAC ports.
- Third-party hardware validation exists for the upstream series on a different
  device sharing this device's exact chip ID and family: `gusfm` tested v5 and v6 of
  the series on a TP-Link EX511 v2 (RTL8367S-VB, chip ID `0x6642`, family D) and
  reported successful switch detection, a stable 1Gbps SGMII CPU link up in 4.6s, 0
  FCS/CRC/drop errors, working VLAN-aware bridging, 20 rounds of VLAN churn without
  loss, and two clean reboot cycles. This is the strongest third-party hardware
  evidence currently available that this patch family works on this exact chip,
  even though it is not this specific device.
- The PR is still in draft, requires 6 reviewer approvals to merge, and has 1 failing
  check as of this writing.

This was initially missed in this project's own research (an earlier search pass
concluded, incorrectly, that PR #19644 did not exist or had the wrong number); it was
confirmed real via direct inspection of the PR page itself, with its full patch list,
author, comment history, and the `gusfm` test report.

**Pending action:** update this tree's `777-0x` patches to the upstream v5/v6
revision before asking anyone to test on physical AX23 v2 hardware, so that any
hardware test result reflects the more-validated patch set rather than the earlier
v1. Not yet done. Tracked as a planned issue in this project's own issue tracker.

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
