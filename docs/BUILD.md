# Build instructions

These instructions reproduce the build this port has been tested against. They cover
**building the firmware image**, not flashing it — see `TESTING.md` for the current
state of hardware validation (as of writing, none of these images have been run on a
physical AX23 v2).

## Prerequisites

Tested on Debian 13 (trixie) with GCC 14.2.0 and GNU Make 4.4.1. OpenWrt's own build
requirements apply — see the
[official OpenWrt build documentation](https://openwrt.org/docs/guide-developer/toolchain/install-buildsystem)
for the full dependency list for your distribution. Packages confirmed present in the
environment this was built in:

```
build-essential gawk libncurses-dev python3 python3-dev unzip zlib1g-dev
```

**Disk space:** budget at least 25-30GB free for a single target build (source tree,
toolchain, and build artifacts).

**Time:** on a 2-core machine, a from-scratch build of this target takes on the order
of hours; an incremental rebuild after a small change (e.g. editing the DTS) took
around 18 minutes in the environment this was tested in. Your mileage will vary
heavily with core count.

## 1. Get an OpenWrt source tree

```sh
git clone https://github.com/openwrt/openwrt.git
cd openwrt
git checkout 98b1185d039344553aaf8270d0661cfad4f0a54d
```

### Base revision and reproducibility

- **Development base revision:** This port was developed and compiled against upstream OpenWrt commit [`98b1185d039344553aaf8270d0661cfad4f0a54d`](https://github.com/openwrt/openwrt/commit/98b1185d039344553aaf8270d0661cfad4f0a54d) ("mt76: update to Git HEAD (2026-10-08)", author Felix Fietkau), which is the upstream parent of the development checkpoint (`b2ab51c08c`).
- Checking out this revision aligns the subtarget (`target/linux/qualcommax/ipq50xx`), kernel patches (`target/linux/generic/pending-6.18`), and build scripts with the state in which this port's patches and DTS were compiled.
- **Reproducibility note:** While pinning this upstream commit eliminates core tree divergence, an end-to-end clean-room build from a fresh clone following only this guide has not yet been independently re-run. Host toolchain versions, feed package snapshots, and `.config` selections can introduce build-time differences.

## 2. Apply this port's patches

Copy the device tree into place:

```sh
cp /path/to/ax23v2-public/target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts \
   target/linux/qualcommax/dts/
```

Apply the switch driver patches (family D / RTL8367D support for `rtl8365mb`):

```sh
for p in /path/to/ax23v2-public/target/linux/generic/pending-6.18/777-*.patch; do
    patch -p1 < "$p"
done
```

Apply the ath11k calibration-data patch:

```sh
patch -p1 < /path/to/ax23v2-public/patches/0001-add-tplink-archer-ax23-v2-caldata.patch
```

Add the device definition block. The content is in
`target/linux/qualcommax/image/ipq50xx-ax23v2-snippet.mk` in this repo, with a comment
indicating where it belongs in the real `ipq50xx.mk` (immediately after the
`mercusys_mr80x-v2` device block and before `tplink_archer-ax55-v1`, confirmed by line
position at the time this was written — if those neighboring devices have moved,
search for them by name instead of by line number). Paste the block into
`target/linux/qualcommax/image/ipq50xx.mk` at that location.

See `docs/DEVICE-TREE.md` for the reasoning behind these patches, not just their
content.

## 3. Configure the build

```sh
make defconfig
```

Then select the device profile. Either via `menuconfig`:

```sh
make menuconfig
# Target System: Qualcomm Atheros QCA/QCN/IPQ/OCTEON...
# Subtarget: IPQ50xx based boards
# Target Profile: TP-Link Archer AX23 v2
```

or directly, by setting in `.config`:

```
CONFIG_TARGET_qualcommax_ipq50xx_DEVICE_tplink_archer-ax23-v2=y
```

and running `make defconfig` again to resolve dependent options.

If you want an initramfs image for non-persistent testing (recommended — see
`TESTING.md` before writing anything to NAND), also enable:

```
CONFIG_TARGET_ROOTFS_INITRAMFS=y
```

## 4. Build

```sh
make -j"$(nproc)"
```

For a first build, consider `make -j1 V=s` instead, or re-running with `V=s` on
failure — a serial build makes it much easier to see which package failed.

## 5. Output

Successful builds produce, under `bin/targets/qualcommax/ipq50xx/`:

```
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-initramfs-factory.ubi
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-initramfs-uImage.itb
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-squashfs-factory.ubi
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-squashfs-sysupgrade.bin
openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2.manifest
```

None of these have been written to a physical device as of this writing. **Do not
flash the `squashfs` images to real hardware before reading `TESTING.md`** — the
proposed first step on real hardware is a non-persistent boot of the
`initramfs-uImage.itb` over UART/TFTP (contingent on test H0 confirming that
OEM U-Boot accepts interactive commands and network image loading), not a NAND write.

## Known build-time caveats

- The switch driver (`rtl8365mb`, with the family-D patches applied) is built directly
  into the kernel in the configuration this was tested with, not as a loadable module.
- `CONFIG_SERIAL_AMBA_PL011` / `_CONSOLE` were enabled in
  `target/linux/qualcommax/config-6.18` specifically to allow booting the initramfs
  image under QEMU's `virt` machine for userspace-level smoke testing. **This does not
  exercise the IPQ5018 SoC, the RTL8367 switch, NAND, or either radio** — a QEMU boot
  proves the initramfs userspace itself isn't broken, nothing about this specific
  hardware. See `TESTING.md`.
- No `board-2.bin`/`firmware-2.bin` was found for the QCN6122 radio in test builds —
  only `m3_fw`. The implication of this is still open; see
  `docs/KNOWN-ISSUES.md` §2.
