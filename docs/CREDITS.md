# Credits

This file separates this project's own work from work carried in from other
authors, so that credit lands where it belongs.

## This project's own work

- `target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts` - device tree
- `target/linux/qualcommax/image/ipq50xx-ax23v2-snippet.mk` - image definition
- `patches/0001-add-tplink-archer-ax23-v2-caldata.patch` - ath11k caldata hotplug cases for this device
- All of `docs/` - written for this repository, except where it describes or
  quotes someone else's work (credited inline and here)

## Carried-in third-party patches

The eight `rtl8365mb` switch driver patches in
`target/linux/generic/pending-6.18/777-01` through `777-08` are **not this
project's own work**. They were written by:

- **Mieczyslaw Nalewaj** (`namiltd@yahoo.com`) - author of all eight patches
  (`777-01` through `777-08`)
- **Fabiano Tassotti** (`fabianotassotti@gmail.com`) - co-signed `777-07`
- **Oleg Gavrilov** (`gabonpivovich@gmail.com`) - co-signed `777-08`

Each patch file keeps its original `From:`/`Signed-off-by:` header, which is
the authoritative record of authorship. This repository carries them because
the AX23 v2's switch (RTL8367SC, "family D") needs the functionality they
add, and the DTS in this tree assumes they're applied - see
`docs/DEVICE-TREE.md`. They are licensed `GPL-2.0-or-later` per the kernel
tree they patch; see each patch file for specifics.

<!--
TODO (repository owner): fill in the concrete source for these eight patches
- e.g. an OpenWrt Gerrit/GitHub PR number, a lore.kernel.org / openwrt-devel
thread, or an upstream fork/branch - and link it here, so anyone reading this
file can go straight to the original submission instead of just the patch
headers.
-->

## Hardware access and research credited elsewhere

- **vram** (OpenWrt forum) - UART access and OEM U-Boot DTB extraction,
  credited in `docs/HARDWARE.md` and referenced from the DTS header. See
  OpenWrt forum thread `t/249493`.
- **EX511 v2** (`kuncy7/openwrt-nss-edma`, branch `ipq50xx-nss`) and
  **AX55 v1** (`kuncy7/openwrt-ax55-v1`) - used as references while writing
  this device's DTS; see `docs/DEVICE-TREE.md` for which values were copied
  versus derived independently.