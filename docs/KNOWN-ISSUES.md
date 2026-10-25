# Known issues, open questions, and licensing notes

Evidence tags used throughout this file, consistent with
[`archer-ax23-v2-port-status.md`](archer-ax23-v2-port-status.md):

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Checked by a command whose output is shown or linked. |
| `[SOURCE]` | Read directly from a file in this tree or a vendor-supplied archive. |
| `[OPEN]` | Unknown, or a hypothesis not yet tested. |

## 1. Switch chip identification (family D)

`[OPEN]` The Ethernet switch reports chip ID `0x6642` (RTL8367D family) via the vendor
`qca-ssdk` kernel module's detection routine, static-analysis-confirmed `[VERIFIED]`.
The exact chip revision has not been read from a physical unit. Upstream
`rtl8365mb` driver support for this specific ID/revision combination has not been
cross-checked against a live device. No conclusion about hardware compatibility should
be drawn until this is confirmed with UART or direct probing.

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
a UART dump to resolve.

## 4. Trunk link speed / SGMII validation

`[OPEN]` MDIO-level detection of the switch does not by itself demonstrate working
Ethernet traffic over the GMAC1 → SGMII → switch CPU port link. This needs to be
tested on physical hardware before any claim of "Ethernet works" is made.

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
`GPL_AX23v2.tar.gz` archive for this device, that directory does not exist — the
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
terms, which do not carry a source-disclosure obligation — so this is not presented
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
different firmware releases) shows **no changes to RTL8367 switch support code** —
every RTL8367-related symbol and string (`rtl8367_proc_reg_rw`, `rtl8367_proc_mib_set`,
`rtl8367_gpio_reset`, etc.) is byte-identical between versions. The ~3.9KB size
difference is fully accounted for by added support for Realtek RTL8221/RTL8226 PHYs
(EEE, Giga-Lite, RTCT cable test) unrelated to this device's switch, plus the updated
build timestamp. This is useful context for anyone comparing behavior across firmware
versions: the switch-relevant code path has been stable across at least these two
releases.
