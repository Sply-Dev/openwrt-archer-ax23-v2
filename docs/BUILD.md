# Build instructions

These instructions describe how to reproduce the OpenWrt build for the TP-Link Archer AX23 v2. They cover **building the firmware images, not flashing them**. See `TESTING.md` for the current hardware-validation status. The port has been validated on physical hardware through v0.4-3 using initramfs booted from RAM via U-Boot/TFTP.

## Prerequisites

Tested on Debian 13 (trixie) with GCC 14.2.0 and GNU Make 4.4.1. OpenWrt's own build requirements apply; see the [official OpenWrt build documentation](https://openwrt.org/docs/guide-developer/toolchain/install-buildsystem) for the full dependency list for your distribution.

Packages confirmed present in the environment used for the build:

```sh
build-essential gawk libncurses-dev python3 python3-dev unzip zlib1g-dev
```

**Disk space:** budget at least 25–30 GB free for a single target build (source tree, toolchain, and build artifacts).

**Time:** on a 2-core machine, a from-scratch build of this target takes on the order of hours. An incremental rebuild after a small change (e.g. editing the DTS) took around 18 minutes in the environment used for testing. Your mileage will vary heavily with core count.

## 1. Get an OpenWrt source tree

```sh
git clone https://github.com/openwrt/openwrt.git
cd openwrt
git checkout 98b1185d039344553aaf8270d0661cfad4f0a54d
```

### Base revision and reproducibility

- **Development base revision:** This port was developed against upstream OpenWrt commit [`98b1185d039344553aaf8270d0661cfad4f0a54d`](https://github.com/openwrt/openwrt/commit/98b1185d039344553aaf8270d0661cfad4f0a54d) ("mt76: update to Git HEAD (2026-10-08)", author Felix Fietkau), identified as the upstream parent of the development checkpoint (`b2ab51c08c`).
- Checking out this revision aligns the subtarget (`target/linux/qualcommax/ipq50xx`), kernel patches (`target/linux/generic/pending-6.18`), and build scripts with the development state against which this port was prepared.
- **Reproducibility note:** Pinning the upstream commit eliminates core source-tree divergence, but an end-to-end clean-room build from a fresh clone following only this guide has not yet been independently re-run. Host toolchain versions, feed package snapshots, and `.config` selections can introduce build-time differences.

## 2. Apply this port's patches

Copy the device tree into place:

```sh
cp /path/to/ax23v2-public/target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts \
   target/linux/qualcommax/dts/
```

### Apply the Realtek switch driver patch series

This port includes the ten-patch **net-next v7** series for the Realtek RTL8365MB DSA driver, numbered `777-01` through `777-10`.

The series introduces chip-family infrastructure, adds RTL8367S-VB support, and includes family-D-specific functionality such as speed configuration, RGMII configuration, VLAN handling, SDS13 PCS support, SerDes re-latching, and L2 LUT access.

Apply all ten patches:

```sh
for p in /path/to/ax23v2-public/target/linux/generic/pending-6.18/777-*.patch; do
    patch -p1 < "$p"
done
```

The patches must be applied to the matching upstream source revision specified in Section 1. In this project, the pre-v7 and v7 labels refer to the same series used for the documented builds; v9 and v10 have not been incorporated or tested here.

### Apply the ath11k calibration-data patch

```sh
patch -p1 < /path/to/ax23v2-public/patches/0001-add-tplink-archer-ax23-v2-caldata.patch
```

### Add default network, factory MAC, and LED configurations

Apply patches 0002 through 0005 to configure networking, factory MAC extraction, and LED triggers:

1. **Network interfaces (LAN/WAN port mapping):**
   ```sh
   patch -p1 < /path/to/ax23v2-public/patches/0002-add-tplink-archer-ax23-v2-network-defaults.patch
   ```
   Groups `lan1`-`lan4` as LAN (`br-lan`) and `wan` as WAN.

2. **Preinit TP-Data mount (for factory MAC):**
   ```sh
   patch -p1 < /path/to/ax23v2-public/patches/0004-add-tplink-archer-ax23-v2-tp-data-mount.patch
   ```
   Mounts the `tp_data` UBIFS NAND volume (`/dev/mtd13`) read-only at `/tmp/tp_data` during preinit.

   > [!IMPORTANT]
   > Ensure that patch tools or manual edits do not leave `.orig` or backup files in `target/linux/qualcommax/ipq50xx/base-files/lib/preinit/`. OpenWrt's preinit loader sources all files in `/lib/preinit/*` alphabetically, and leftover `.orig` files will silently redefine functions and override the intended board definitions.

3. **Factory MAC assignment:**
   ```sh
   patch -p1 < /path/to/ax23v2-public/patches/0003-add-tplink-archer-ax23-v2-label-mac.patch
   ```
   Reads the 6-byte binary factory MAC from `/tmp/tp_data/default-mac` in `ipq50xx_setup_macs()`, assigning base MAC to `lan` and `base + 1` to `wan`.

4. **LED network activity triggers:**
   ```sh
   patch -p1 < /path/to/ax23v2-public/patches/0005-add-tplink-archer-ax23-v2-led-defaults.patch
   ```
   Configures `white:lan` to trigger on `br-lan` and `white:wan` on `wan` via `01_leds`.

### Add the device definition

The device definition block is provided in:

`target/linux/qualcommax/image/ipq50xx-ax23v2-snippet.mk`

Paste its contents into the upstream `target/linux/qualcommax/image/ipq50xx.mk`, immediately after the `mercusys_mr80x-v2` device block and before `tplink_archer-ax55-v1`.

These neighboring device definitions are reference points; search for them by name if their positions have changed.

See `docs/DEVICE-TREE.md` for the reasoning behind the device tree and switch configuration.

## 3. Configure the build

```sh
make defconfig
```

Then select the device profile using `menuconfig`:

```sh
make menuconfig
```

Select:

```text
Target System: Qualcomm Atheros QCA/QCN/IPQ/OCTEON...
Subtarget: IPQ50xx based boards
Target Profile: TP-Link Archer AX23 v2
```

Alternatively, set the profile directly in `.config`:

```text
CONFIG_TARGET_qualcommax_ipq50xx_DEVICE_tplink_archer-ax23-v2=y
```

Then run `make defconfig` again to resolve dependent options.

For an initramfs image intended for non-persistent testing, also enable:

```text
CONFIG_TARGET_ROOTFS_INITRAMFS=y
```

**Hardware validation through v0.4-3 was conducted using the initramfs image booted from RAM.** See `TESTING.md` for the full test results and remaining items.

## 4. Build

```sh
make -j"$(nproc)"
```

For a first build, consider:

```sh
make -j1 V=s
```

Alternatively, re-run with `V=s` after a failure. A serial build makes it easier to identify which package failed.

## 5. Output

Successful builds produce artifacts under:

`bin/targets/qualcommax/ipq50xx/`

```text
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-initramfs-factory.ubi
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-initramfs-uImage.itb
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-squashfs-factory.ubi
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-squashfs-sysupgrade.bin
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2.manifest
```

### Flashing restrictions

**Generating an image does not mean that it is safe to flash.**

The port has been validated in hardware through v0.4-3 via non-persistent initramfs RAM boots (loaded via U-Boot/TFTP). Persistent NAND installation has not been validated.

- The `squashfs-factory.ubi` and `squashfs-sysupgrade.bin` images are **not authorized for flashing**.
- Do not write any generated image to NAND or attempt a persistent installation. Dual-boot A/B partition switching (`tp_boot_idx`) is not yet implemented or tested in `platform.sh`.
- Always verify hardware behavior using RAM-only initramfs boots (`initramfs-uImage.itb`) before considering any flash operations.

Read `TESTING.md` before attempting any hardware testing.

## Known build-time caveats

- **Leftover patch files in preinit:** As noted above, never leave `.orig` or backup files in `base-files/lib/preinit/` as the OpenWrt preinit sequence will blindly source them.
- The `rtl8365mb` switch driver is built directly into the kernel in the tested configuration, not as a loadable module. The applied net-next v7 series contains support for multiple chip families; the presence of RTL8367S-VB support in the driver does not establish that this specific hardware configuration has been validated.
- `CONFIG_SERIAL_AMBA_PL011` / `_CONSOLE` were enabled in `target/linux/qualcommax/config-6.18` specifically to allow booting the initramfs image under QEMU's `virt` machine for userspace-level smoke testing. **This does not exercise the IPQ5018 SoC, RTL8367 switch, NAND, or either radio.** A QEMU boot only demonstrates that the initramfs userspace itself is not broken. See `TESTING.md`.
- Wi-Fi compatibility was deliberately outside current testing scope. While caldata offsets (0x1000 for IPQ5018 and 0x26800 for QCN6122 in `0:ART`) have been confirmed bit-for-bit against hardware dumps, the current ath11k driver fails to fetch board-data with error `-12`. See `docs/KNOWN-ISSUES.md`, Section 2.

## Proposed constrained-memory/recovery contribution (review branch only)

The optional patches `0006` through `0012` carry ath11k low-memory ring sizing, partial DMA/datapath cleanup, and IPQ5018 Q6 multi-PD recovery changes proposed for review. They are not part of the previously hardware-tested Sply build unless explicitly applied. The patches add OpenWrt patch files under the ath11k mac80211 backports and qualcommax kernel patch series; apply them at the OpenWrt source root after the existing device patches:

```sh
for p in /path/to/ax23v2-public/patches/000{6..9}-*.patch \
         /path/to/ax23v2-public/patches/001{0..2}-*.patch; do
    git apply --check "$p" && git apply "$p"
done
```

### Focused PR #2 integration check (2026-11-22)

The seven wrapper patches in `contrib/ax23-wifi-memory-recovery` were applied in the documented order to OpenWrt commit `98b1185d039344553aaf8270d0661cfad4f0a54d`; all seven `git apply --check` and apply steps passed. The target source reports Linux `6.18.55`. OpenWrt's mac80211 package pins backports `7.2` with source hash `6ec76a4cb0988b5382b2fc5053610a56ada90b8ef6a5a4f2807cd433badb9454`.

The following scoped target steps completed successfully in an isolated worktree using the AX23 target configuration and copied local download/staging caches (not a clean-room or full firmware build):

- `make -j2 V=s target/linux/prepare`
- `make -j2 V=s package/kernel/mac80211/prepare`
- `make -j2 V=s target/linux/compile`
- `make -j2 V=s package/kernel/mac80211/compile`

The compiled Linux object `drivers/remoteproc/qcom_q6v5_mpd.o` contains `q6_wcss_recover_userpds`; the backports build produced `ath11k/dp.o`, `dp_tx.o`, `dp_rx.o`, and `ath11k.ko` (Linux 6.18.55). This verifies compilation and inclusion in these target objects/modules, not runtime recovery or radio operation.

Focused tests passed against the integration-prepared sources: the ath11k ring-allocation check, the eight-scenario Q6 recovery model, and `python3 -m unittest discover -s tests/host -p 'test_*.py'` (13 tests). These are source/model tests, not a faithful concurrent-kernel or DMA-hardware test. The first mac80211 compile attempt stopped earlier while rebuilding host `apk`: copied `.pc/.la` metadata contained an old absolute staging path, adding a duplicate host include directory and hiding glibc endian helpers. After correcting only that metadata in the isolated build tree and regenerating the host package, the retry and mac80211 target completed. The PR source and standalone checkout were not altered by that repair.

This check does not claim a complete firmware build, resolve ath11k board-file `-12`, validate either radio on hardware, prove kernel deadlock freedom, or replace Sply's hardware testing. The Q6 scenario harness remains a model. See [`CONTRIBUTION-INVENTORY.md`](CONTRIBUTION-INVENTORY.md) for the full 27-patch disposition.
