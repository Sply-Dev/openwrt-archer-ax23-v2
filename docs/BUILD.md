# Build instructions

These instructions describe how to reproduce the OpenWrt build for the TP-Link Archer AX23 v2. They cover **building the firmware images, not flashing them**. See `TESTING.md` for the current hardware-validation status. The v0.2 initramfs booted from RAM via U-Boot/TFTP on 2026-11-10. The v0.3 test image has been built, with no v0.3 hardware result documented yet.

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

### Add the default LAN/WAN mapping

The AX23 v2 exposes DSA ports named lan1, lan2, lan3, lan4, and wan. Add the
matching board case to ipq50xx board defaults:

    patch -p1 < /path/to/ax23v2-public/patches/0002-add-tplink-archer-ax23-v2-network-defaults.patch

This groups lan1-lan4 as LAN and wan as WAN. It does not assign interface MAC
addresses; the AX23 v2 MAC source and offsets remain unresolved.

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

**The v0.2 initramfs was booted from RAM on physical hardware.** See `TESTING.md` for the result and remaining validation.

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

The v0.2 initramfs image booted non-persistently on a physical AX23 v2. No persistent image or v0.3 hardware result is documented.

- The `squashfs-factory.ubi` and `squashfs-sysupgrade.bin` images are **not authorized for flashing**.
- Do not write any generated image to NAND or attempt a persistent installation.
- U-Boot console access and TFTP loading were demonstrated with the v0.2 initramfs. Further testing should identify the exact image revision and record the observed link and traffic behavior.
- The documented v0.2 boot loaded initramfs into RAM; it did not validate NAND installation.

Read `TESTING.md` before attempting any hardware testing.

## Known build-time caveats

- The `rtl8365mb` switch driver is built directly into the kernel in the tested configuration, not as a loadable module. The applied net-next v7 series contains support for multiple chip families; the presence of RTL8367S-VB support in the driver does not establish that this specific hardware configuration has been validated.
- `CONFIG_SERIAL_AMBA_PL011` / `_CONSOLE` were enabled in `target/linux/qualcommax/config-6.18` specifically to allow booting the initramfs image under QEMU's `virt` machine for userspace-level smoke testing. **This does not exercise the IPQ5018 SoC, RTL8367 switch, NAND, or either radio.** A QEMU boot only demonstrates that the initramfs userspace itself is not broken. See `TESTING.md`.
- Wi-Fi compatibility was deliberately outside the v0.2 test scope. The v0.2 log records board-data loading failures for the IPQ5018 and QCN6122 radios; the cause has not been established. See `docs/KNOWN-ISSUES.md`, Section 2.
