# Build instructions

These instructions describe how to reproduce the OpenWrt build for the TP-Link Archer AX23 v2. They cover **building the firmware images, not flashing them**. See `TESTING.md` for the current hardware-validation status. The port has been validated on physical hardware through v0.5 using initramfs booted from RAM via U-Boot/TFTP.

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

Copy all ten kernel patches into `target/linux/generic/pending-6.18/`:

```sh
cp /path/to/ax23v2-public/target/linux/generic/pending-6.18/777-*.patch \
   target/linux/generic/pending-6.18/
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

**Hardware validation through v0.5 was conducted using the initramfs image booted from RAM.** See `TESTING.md` for the full test results and remaining items.

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

The port has been validated in hardware through v0.5 via non-persistent initramfs RAM boots (loaded via U-Boot/TFTP). Persistent NAND installation has not been validated.

- The `squashfs-factory.ubi` and `squashfs-sysupgrade.bin` images are **not authorized for flashing**.
- Do not write any generated image to NAND or attempt a persistent installation. Dual-boot A/B partition switching (`tp_boot_idx`) is not yet implemented or tested in `platform.sh`.
- Always verify hardware behavior using RAM-only initramfs boots (`initramfs-uImage.itb`) before considering any flash operations.

Read `TESTING.md` before attempting any hardware testing.

## Known build-time caveats

- **Leftover patch files in preinit:** As noted above, never leave `.orig` or backup files in `base-files/lib/preinit/` as the OpenWrt preinit sequence will blindly source them.
- The `rtl8365mb` switch driver is built directly into the kernel in the tested configuration, not as a loadable module. The applied net-next v7 series contains support for multiple chip families; the presence of RTL8367S-VB support in the driver does not establish that this specific hardware configuration has been validated.
- `CONFIG_SERIAL_AMBA_PL011` / `_CONSOLE` were enabled in `target/linux/qualcommax/config-6.18` specifically to allow booting the initramfs image under QEMU's `virt` machine for userspace-level smoke testing. **This does not exercise the IPQ5018 SoC, RTL8367 switch, NAND, or either radio.** A QEMU boot only demonstrates that the initramfs userspace itself is not broken. See `TESTING.md`.
- Wi-Fi compatibility was deliberately outside early testing scope (v0.1 through v0.5). While caldata offsets (0x1000 for IPQ5018 and 0x26800 for QCN6122 in `0:ART`) were confirmed bit-for-bit against hardware dumps, earlier builds lacked `board-2.bin` packages and low-memory `ath11k` ring sizing. See the `v0.6-wifi-integration` section below and `docs/KNOWN-ISSUES.md`, Section 2.

## 6. `v0.6-wifi-integration`: UNIPHY preconfig (`0006`) and Wi-Fi / Q6 recovery series (`0007`–`0017`)

After applying patches `0001` through `0005` and adding the device definition snippet to `target/linux/qualcommax/image/ipq50xx.mk` (Section 2), apply the v0.5 UNIPHY PCS preconfiguration patch (`0006`) and the `v0.6-wifi-integration` patches (`0007` through `0017`) at the OpenWrt source root:

```sh
git apply --check /path/to/ax23v2-public/patches/0006-qualcommax-ipq50xx-uniphy-pcs-preconfig.patch && \
git apply /path/to/ax23v2-public/patches/0006-qualcommax-ipq50xx-uniphy-pcs-preconfig.patch

for p in /path/to/ax23v2-public/patches/000{7..9}-*.patch \
         /path/to/ax23v2-public/patches/001{0..7}-*.patch; do
    git apply --check "$p" && git apply "$p"
done
```

### Supplying local `board-2.bin` files for `ipq-wifi-tplink_archer-ax23-v2` (patch `0015`)

Patch `0015` creates `package/firmware/ipq-wifi-tplink-archer-ax23-v2/` and adds `ipq-wifi-tplink_archer-ax23-v2` to `DEVICE_PACKAGES`. Because board calibration / BDF payloads are proprietary and not stored in this repository, generate the two `board-2.bin` files locally (covering both `qmi-board-id=255` and the decimal stock selectors `36` for IPQ5018 / `96` for QCN6122, with separate outer `ATH11K_BD_IE_BOARD` TLVs per selector) and place them at:

```sh
cp /path/to/board-2-ipq5018-FINAL.bin \
   package/firmware/ipq-wifi-tplink-archer-ax23-v2/files/board-tplink_archer-ax23-v2.ipq5018
cp /path/to/board-2-qcn6122-FINAL.bin \
   package/firmware/ipq-wifi-tplink-archer-ax23-v2/files/board-tplink_archer-ax23-v2.qcn6122
```

### Host-side regression checks (`tests/host/`)

Before or after compiling `target/linux` and `package/kernel/mac80211`, the host-model unit and regression checks can be run against the prepared kernel and backports sources:

```sh
python3 /path/to/ax23v2-public/tests/host/check_ath11k_ring_alloc.py \
    build_dir/target-*/linux-qualcommax_ipq50xx/mac80211-*/backports-*/drivers/net/wireless/ath/ath11k/dp.c
python3 /path/to/ax23v2-public/tests/host/check_ath11k_cleanup.py \
    build_dir/target-*/linux-qualcommax_ipq50xx/mac80211-*/backports-*/drivers/net/wireless/ath/ath11k/dp.c
python3 /path/to/ax23v2-public/tests/host/check_mpd_recovery.py \
    build_dir/target-*/linux-qualcommax_ipq50xx/linux-*/drivers/remoteproc/qcom_q6v5_mpd.c
python3 -m unittest discover -s /path/to/ax23v2-public/tests/host -p 'test_*.py'
```
