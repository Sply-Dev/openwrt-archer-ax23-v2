# Credits

This file separates this project's own work from work carried in from other
authors, so that credit lands where it belongs.

## This project's own work

- `target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts` - device tree
- `target/linux/qualcommax/image/ipq50xx-ax23v2-snippet.mk` - image definition
- `patches/0001-add-tplink-archer-ax23-v2-caldata.patch` - ath11k caldata hotplug cases for this device
- `patches/0002-add-tplink-archer-ax23-v2-network-defaults.patch` - AX23 v2 LAN/WAN interface roles
- `patches/0003-add-tplink-archer-ax23-v2-label-mac.patch` - factory MAC address retrieval from tp_data
- `patches/0004-add-tplink-archer-ax23-v2-tp-data-mount.patch` - preinit mount for tp_data UBIFS volume
- `patches/0005-add-tplink-archer-ax23-v2-led-defaults.patch` - LAN/WAN netdev trigger defaults
- All of `docs/` - written for this repository, except where it describes or
  quotes someone else's work (credited inline and here)

## Community testing and hardware validation

- **Veraxis** (OpenWrt forum) - Extensive physical hardware validation on an
  Archer AX21 v5 (US variant identifying as AX23 v2 hardware) using UART and
  TFTP RAM boots. Confirmed initial boots (v0.2), `br-lan` switch membership and
  LAN-to-LAN forwarding (v0.3), LED polarity and LAN/WAN `netdev` link/activity
  triggers (v0.4/v0.4-2), direct WAN external connectivity (v0.4-2/v0.4-3), and
  automated preinit factory MAC address reading from `tp_data/default-mac` (v0.4-3).
  Active testing and feedback documented in OpenWrt forum thread `t/254876`.

## Carried-in third-party patches

The ten `rtl8365mb` switch driver patches in
`target/linux/generic/pending-6.18/777-01` through `777-10` are **not this
project's own work**. The files currently carry `net-next v7` headers
and correspond to the pre-v7/v7 series used in this project's builds
and tests (OpenWrt PR [#19644](https://github.com/openwrt/openwrt/pull/19644)).
Those labels are equivalent in this project; they do not identify two
separately validated implementations. v9 and v10 have not been
incorporated or tested here. The authors are:

- **Mieczyslaw Nalewaj** (`namiltd@yahoo.com`) - author of all ten patches
  (`777-01` through `777-10`)
- **Fabiano Tassotti** (`fabianotassotti@gmail.com`) - co-developed `777-07`
  (`Co-developed-by:`/`Signed-off-by:`)

The following reviewers are credited in the carried patch headers:

- **Linus Walleij** (`linusw@kernel.org`) - `Reviewed-by` on `777-01`, `777-02`,
  and `777-07`
- **Luiz Angelo Daros de Luca** (`luizluca@gmail.com`) - `Reviewed-by` on
  `777-01` and `777-02`

Each patch file keeps its original `From:`/`Signed-off-by:`/`Reviewed-by:`
header, which records authorship and review. See the patch files for
exact attribution. This repository carries them because the AX23 v2's switch (RTL8367SC per
static chip-ID analysis, "family D" - see `KNOWN-ISSUES.md` §1; RTL8367SC is
only the commercial name printed on the unit, not the driver-level chip
identity) needs the functionality they add, and the DTS in this tree assumes
they are applied; see [`DEVICE-TREE.md`](DEVICE-TREE.md). They are licensed `GPL-2.0-or-later`
per the kernel tree they patch; see each patch file for specifics.

> **Note on the earlier (v1) revision:** this repository previously carried
> an early v1 revision of this same series (eight patches, `777-01` through
> `777-08`). That revision was also written by Mieczyslaw Nalewaj, with
> `Fabiano Tassotti` and `Oleg Gavrilov` credited as co-signers on individual
> patches. It was replaced in full by the current ten-patch series; see
> [`KNOWN-ISSUES.md`](KNOWN-ISSUES.md) §8 for what changed between revisions,
> and §8.1-8.2 for how this series relates to the separate, already-merged
> Johan Alvarado SerDes/PCS series.

## Hardware access and research credited elsewhere

- **Nihilokrat** (OpenWrt forum) - PCB and hardware teardown photographs,
  credited in [`README.md`](../README.md). See OpenWrt forum thread `t/225168`.
- **vram** (OpenWrt forum) - UART access and OEM U-Boot DTB extraction,
  credited in [`HARDWARE.md`](HARDWARE.md) and referenced from the DTS header. See
  OpenWrt forum thread `t/249493`.
- **EX511 v2** (`kuncy7/openwrt-nss-edma`, branch `ipq50xx-nss`) and
  **AX55 v1** (`kuncy7/openwrt-ax55-v1`) - used as references while writing
  this device's DTS; see [`DEVICE-TREE.md`](DEVICE-TREE.md) for which values were copied
  versus derived independently.
- **gusfm** (OpenWrt forum) - reported testing the v5/v6 revision of the
  `777-0x` series on a TP-Link EX511 v2 (same switch family), referenced in
  [`KNOWN-ISSUES.md`](KNOWN-ISSUES.md) §8.

## Proposed AX23 Wi-Fi memory/recovery contribution

Patches `0006` through `0012` and their host-side regression checks are proposed contributions carried from the independent [`john35413/openwrt-archer-ax23-v2-build`](https://github.com/john35413/openwrt-archer-ax23-v2-build) engineering project. The patch mail headers retain their original author/sign-off metadata; this repository does not claim sole authorship. The series was developed with Claude and Codex-assisted engineering and independently reviewed in that project. Its separate offline build and model tests are not hardware validation of Sply's tree. See [`CONTRIBUTION-INVENTORY.md`](CONTRIBUTION-INVENTORY.md) for patch-by-patch origin and disposition.
