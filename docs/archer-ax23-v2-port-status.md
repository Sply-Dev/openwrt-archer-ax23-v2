# TP-Link Archer AX23 v2 - OpenWrt port status

Status document for the `tplink_archer-ax23-v2` device (target `qualcommax/ipq50xx`).
Last reviewed: 2026-10-17.

> **A functional boot on a physical TP-Link Archer AX23 v2 has NOT been demonstrated.**
> Everything recorded below is a build result or a static inspection of files and build
> artifacts. No image from this tree has been run on the real device, and no result in this
> document should be read as hardware validation. A QEMU boot would not change that: it
> does not exercise this SoC, switch, NAND or radios.

> **Snapshot Note:** This document is an audit snapshot of the private development build tree (`/workspace/openwrt`) recorded on 2026-10-17. References to untracked files, backups, logs, or repository anomalies in section R17 and Appendix A reflect that private working environment at review time and do not exist in this clean public repository.

## Scope and evidence conventions

Baseline reviewed:

- Detached `HEAD` at `b2ab51c08c` ("checkpoint: preserve Archer AX23 v2 port work"), on top of
  upstream `98b1185d03` ("mt76: update to Git HEAD (2026-10-08)").
- At review time the working tree had 2 modified tracked files and 10 untracked paths
  (Appendix A). They pre-date this document and were left untouched.
- This document was produced without modifying the DTS, patches, scripts, configs, images,
  backups or calibration data. The only change made is the creation of this file.

Evidence tags used throughout:

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Checked by a command run during this review. Commands are in Appendix B; results in section 2. |
| `[SOURCE]` | Read directly from a file in this tree (tracked or untracked). Not exercised. |
| `[REPORTED]` | Carried over from earlier project sessions / notes. Not re-checked in this review. |
| `[OPEN]` | Unknown, or a hypothesis. |

## 1. Existing implementation

### 1.1 Committed in `b2ab51c08c` (13 files, +2199 / -1)

| Component | Path | Summary |
|---|---|---|
| Device tree | `target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts` (445 lines) | See 1.2. `[SOURCE]` |
| Image definition | `target/linux/qualcommax/image/ipq50xx.mk` | `Device/tplink_archer-ax23-v2`: `FitImageLzma` + `UbiFit`, `DEVICE_DTS_CONFIG := config@mp02.1`, `BLOCKSIZE 128k`, `PAGESIZE 2048`, `NAND_SIZE 128m`, `IMAGE_SIZE 54784k`, `DEVICE_PACKAGES := ath11k-firmware-ipq5018-qcn6122 kmod-dsa-rtl8365mb`, plus an `initramfs-factory.ubi` artifact. `[SOURCE]` |
| Switch driver patches | `target/linux/generic/pending-6.18/777-01 ... 777-08` | Eight local patches to `rtl8365mb`: detect RTL8367S-VB; set speed, get pvid, set/clear pvid, 4k VLAN, RGMII mode for "family D"; family D SDS13 PCS support; re-latch of the family D SerDes. Not upstream. `[SOURCE]` |
| Kernel config | `target/linux/qualcommax/config-6.18` | Adds `NET_DSA_REALTEK`, `NET_DSA_REALTEK_MDIO`, `NET_DSA_REALTEK_RTL8365MB` as `=y`, and `SERIAL_AMBA_PL011` + `_CONSOLE` (comment in file: QEMU virt serial console for AX23 initramfs testing). `[SOURCE]` |
| Preinit | `.../ipq50xx/base-files/lib/preinit/09_mount_tp_data` | Adds `tplink,archer-ax23-v2` to the boards whose `tp_data` UBIFS volume is attached and mounted read-only in preinit. `[SOURCE]` |
| ath11k caldata | `.../ipq50xx/base-files/etc/hotplug.d/firmware/11-ath11k-caldata` | AX23 v2 cases: 2.4 GHz from `0:ART` offset `0x1000` (len `0x20000`), MAC = `default-mac` minus 1; 5 GHz (QCN6122) from `0:ART` offset `0x26800` (len `0x20000`), MAC = `default-mac` minus 2. In `HEAD` each case appears twice (see 1.3). `[SOURCE]` |

### 1.2 What the device tree describes `[SOURCE]`

- Includes `ipq5018.dtsi`, `ipq5018-ess.dtsi`, `ipq5018-qcn6122.dtsi`. `compatible = "tplink,archer-ax23-v2", "qcom,ipq5018"`.
- Console: `serial0` = `blsp1_uart1`, 115200n8, GPIO28 (RX) / GPIO29 (TX).
- Ethernet: `gmac0` disabled; `gmac1` SGMII, fixed-link 1000/full; `uniphy0` with 25 MHz reference clock; `mdio1` on GPIO36 (MDC) / GPIO37 (MDIO).
- Switch: `realtek,rtl8365mb` at MDIO1 address 29, reset on GPIO33 (active low). Ports: 0 = `wan`, 1-4 = `lan1`-`lan4`, 6 = `cpu` (`ethernet = <&gmac1>`, SGMII fixed-link 1000/full).
- Wi-Fi: `&wifi` (IPQ5018 internal, 2.4 GHz) and `&wifi1` (QCN6122, 5 GHz), calibration variant `"TP-Link-Archer-AX23-v2"`, `ath11k-fw-memory-mode = <2>` on both, BDF addresses `0x4c400000` / `0x4d100000`, `m3-dump-addr = <0x4df00000>` on `wifi1`; `q6v5_wcss` `boot-args = <0x2 0x4 0x2 0x1b 0x0 0x0>`.
- NAND: SPI-NAND on `qpic_nand`, ECC strength 4 / step 512, 16 fixed partitions (listing in section 2, check S6). `0:BOOTCONFIG`, `0:BOOTCONFIG1`, `0:APPSBLENV`, `rootfs`, `rootfs_1`, `data` are writable; the rest are `read-only`.
- Inputs/LEDs: reset key on GPIO14 (active low, `KEY_RESTART`); LEDs on GPIO10 (power, default on), 11 (5 GHz, trigger `phy0tpt`), 12 (WAN amber), 13 (WAN white), 22 (WPS), 32 (LAN); all declared `GPIO_ACTIVE_HIGH`.
- `chosen`: `bootargs-append = " root=/dev/ubiblock0_1 coherent_pool=2M"`.

### 1.3 Uncommitted working-tree changes (pre-existing) `[SOURCE]`

- `11-ath11k-caldata`: removes one of two identical AX23 v2 blocks in each of the two firmware sections (IPQ5018 `c000000` and QCN6122 `b00a040`). `HEAD` has four AX23 v2 labels; the working tree has two. In a shell `case`, the first matching label wins, so the duplicates in `HEAD` are redundant, not conflicting.
- `ipq50xx/config-default`: adds `CONFIG_REALTEK_PHY_HWMON=n`, `CONFIG_LED_TRIGGER_PHY=n`, `CONFIG_PCS_QCA_UNIPHY=y`.

### 1.4 Build outputs (untracked) `[SOURCE]`

`ax23-images-20261015/` (copy of `bin/targets/qualcommax/ipq50xx/`):

| Image | Size (bytes) | SHA-256 |
|---|---|---|
| `...ax23-v2-initramfs-uImage.itb` | 12,136,608 | `f21298a7875bd0bbf9fe423d4e344b017e842b97b8db4ca6e85817aa39d5300f` |
| `...ax23-v2-initramfs-factory.ubi` | 12,845,056 | `b7acda7f598ce577df1bf770b784ddd4e578d9c7deb1bdab1d54b224cf30b645` |
| `...ax23-v2-squashfs-sysupgrade.bin` | 12,441,887 | `d9b79212689bb42f35334d51e23382a99729467a140ed6598f08dde5c50831b8` |
| `...ax23-v2-squashfs-factory.ubi` | 13,238,272 | `19ab4e07946e96d348bc2c581afcc1e598b6a32e37dde31d17343d78c5f6af14` |

Also present: `profiles.json`, `sha256sums`, `*.manifest`, `config.buildinfo`, `feeds.buildinfo`, `version.buildinfo`, `packages/`.

### 1.5 Not implemented `[VERIFIED]` by search (S11)

- No `tplink,archer-ax23-v2` case in `board.d/02_network` (no LAN/WAN interface assignment, no MAC assignment), `board.d/01_leds`, or `lib/upgrade/platform.sh`.
- No AX23-specific board-data package (`ipq-wifi-*`) in `DEVICE_PACKAGES`; the AX55 v1 entry has one.
- No MAC source in the DTS (no `nvmem-cells` / `mac-address` for `gmac1`).

## 2. Static checks performed

All results below come from commands run against files in this tree (Appendix B). None of them
involve the device.

| ID | Check | Result | What it does NOT show |
|---|---|---|---|
| S1 | Build completion | `build.exit` = `0`; `build.log` ends with image generation, package index and checksum steps. | That the build output is correct, only that make finished. |
| S2 | Image integrity | `sha256sum -c sha256sums` in `ax23-images-20261015/`: 9/9 `OK`. The four images in `bin/targets/...` are byte-identical (SHA-256) to the archived copies. | Anything about content correctness. |
| S3 | Build provenance | `profiles.json`: `git_commit = b2ab51c08c145274e3c28ce93ddca45bd548388b`, `version_code = r37094+1-98b1185d03`, kernel `6.18.55`, `supported_devices = ["tplink,archer-ax23-v2"]`. | That the tree was clean when built (see S10, R12). |
| S4 | FIT structure of the initramfs image | `mkimage -l`: `kernel-1` (AArch64, Linux, lzma, load/entry `0x41000000`, 12,108,812 bytes), `fdt-1` (26,381 bytes), default configuration `config@mp02.1` - matches `DEVICE_DTS_CONFIG`. The FIT "Created" date equals the commit date (derived from `SOURCE_DATE_EPOCH`), not the build time. | That the OEM U-Boot accepts this FIT (config name `mp02.1` is from OEM analysis, `[REPORTED]`). |
| S5 | DTB consistency | The DTB in `build_dir/.../image-ipq5018-archer-ax23-v2.dtb` has SHA-1 `8179b06809cd66bebd5db360229b152e675cdb17`, identical to the `fdt-1` SHA-1 in the FIT. Decompiled with the tree's `dtc`: `model`, `compatible`, `realtek,rtl8365mb` node with `reset-gpios = <0x0b 0x21 0x01>` (GPIO33, active low), port labels `wan`/`lan1`-`lan4`/`cpu`, calibration variant and `fw-memory-mode = <2>` on both radios, `q6v5_wcss` `boot-args`, `bootargs-append` - all as in the DTS. No `mac-address` / `local-mac-address` property exists anywhere in the compiled DTB (the only `nvmem-cells` belongs to the thermal sensor). | That the described hardware matches the real board. |
| S6 | Partition table | The 16 NAND partitions in the DTS are contiguous with no gap or overlap, ending at `0x7e40000` (126.25 MiB of 128 MiB). `rootfs` and `rootfs_1` are `0x3580000` bytes each, equal to `IMAGE_SIZE := 54784k` (56,098,816 bytes) and to `file_size_limits.image` in `profiles.json`. | That the offsets match the real NAND layout (they come from OEM analysis, `[REPORTED]`). The last 0x1c0000 bytes are not described. |
| S7 | Kernel configuration actually used | Build-tree `.config`: `NET_DSA_REALTEK=y`, `NET_DSA_REALTEK_MDIO=y`, `NET_DSA_REALTEK_RTL8365MB=y`, `PCS_QCA_UNIPHY=y`, `SERIAL_AMBA_PL011=y` (+ console), `REALTEK_PHY_HWMON` and `LED_TRIGGER_PHY` unset. The switch driver is built in (no `.ko`). | That the driver works. |
| S8 | Switch patches present in the build tree | All eight `777-0x` patches exist with subjects `[PATCH 1/8]` ... `[PATCH 8/8]`. A case-insensitive keyword search (`RTL8367S`, `family_d`, `sds13`) in the build tree's `rtl8365mb_main.c` returns 22 matches. | This is a keyword match, not a functional or patch-order check. |
| S9 | Shell syntax | `sh -n` passes for `09_mount_tp_data` and `11-ath11k-caldata`, both for the `HEAD` version and for the working-tree version. | Syntax only. Neither script was executed, and the extracted offsets were not validated against real ART contents. |
| S10 | What the images contain (caldata) | The staged rootfs in `build_dir/.../root-qualcommax` has 4 AX23 v2 labels in `11-ath11k-caldata` (the `HEAD` version). The working tree, edited later (mtime 2026-10-16 03:19, after the images at 2026-10-15 22:07), has 2. The images themselves were not unpacked in this review. | Consistent with the images not containing the uncommitted caldata cleanup; not a check of the image payload. |
| S11 | Missing integration points | No `ax23` match in `02_network`, `01_leds`, `platform.sh`. In `platform.sh`, an unlisted board falls to the `*)` branch (`default_do_upgrade`), and `platform_check_image` returns 0 unconditionally. The AX55 v1 branch, by contrast, selects `rootfs` / `rootfs_1` and sets `tp_boot_idx`. | How `default_do_upgrade` behaves on this board (untested). |

Not checked in this review: `dtc` warning output, rootfs/package contents inside the images
(an earlier inspection is `[REPORTED]` in R7), any QEMU run (no QEMU log is recorded in the
repository, so no QEMU result is claimed), and the origin of the root-owned `core.8` / `core.9`
and `<stdin>.s` files.

## 3. Pending tests on real hardware

Status of every item: **not run**. Ground rules (`[REPORTED]` project rules): no firmware is
written to the router without explicit authorization from the project owner; tests H1-H9 are
designed to be non-persistent.

| ID | Test | Needs | Pass criterion |
|---|---|---|---|
| H0 | Preconditions (not a test) | Console access to the board (UART header JP1; level-shifter SMDs reported removed by the vendor), a way to load an image without flashing, a recovery plan and a backup of the OEM NAND contents. | `[OPEN]` Whether the OEM U-Boot accepts console input and can load a FIT over the network is not established; the non-persistent initramfs path is a hypothesis. |
| H1 | Non-persistent boot of `initramfs-uImage.itb` | H0 | Kernel starts, serial console output at 115200, userspace reached. |
| H2 | Kernel log review | H1 | NAND partitions match section 2/S6, no oops/panic, ESS/UNIPHY initialise. |
| H3 | Switch detection | H1 | `rtl8365mb` reports a chip ID/version and registers `wan`, `lan1`-`lan4`, `cpu`. Settles the open question 0x6642 vs 0x6367 (R1). |
| H4 | CPU link (GMAC1 to switch port 6, SGMII) | H3 | Link up; ping through a LAN port with static addressing; sustained traffic (e.g. iperf) without errors or link drops. MDIO detection alone does not prove this. |
| H5 | Physical port mapping | H3 | Each RJ45 port matches its DTS label (cable swap test); negotiated speeds 10/100/1000. |
| H6 | `tp_data` and MAC | H1 | `tp_data` attaches and mounts read-only in preinit; `default-mac` readable. LAN/WAN MAC assignment additionally needs a `02_network` case (1.5). |
| H7 | 2.4 GHz radio | H1 | ath11k loads; caldata extracted from `0:ART` at `0x1000`; beacons; a client associates. Check also on a unit with erased ART if available. |
| H8 | 5 GHz radio (QCN6102 / QCN6122 firmware) | H1 | Firmware and board data load; AP mode works; stable over a defined soak period (the OEM `boot-args` are there to avoid a reported crash at ~59 s, `[REPORTED]`). |
| H9 | Reset button and LEDs | H1 | Button event on GPIO14; confirm LED polarity and which LED each GPIO drives. |
| H10 | Persistent install and rollback | Authorization + a designed `platform.sh` case | Image written to the inactive slot, boot index switched, boots, and return to OEM firmware is demonstrated. Do not attempt before the sysupgrade path exists (R10). |

## 4. Risks, hypotheses and known limitations

**Hardware identification**

- R1 `[OPEN]` The switch is believed to be an RTL8367SC/RTL8367D-family part with chip ID `0x6642`, but the ID has not been read from the physical unit; `0x6367` is also on the table. From static analysis of the vendor `qca-ssdk.ko`, ID `0x6642` maps to internal type 4, which by itself does not prove functional support. `[REPORTED]`
- R15 Provenance: the DTS header lists "Physical UART access logs" among its sources. According to project notes, the UART and U-Boot DTB data came from third-party forum reports, not from first-hand access on this project's unit. The header should be corrected before anything is published. `[REPORTED]`

**Switch and Ethernet**

- R2 The eight `777-xx` patches change `rtl8365mb`, a driver shared with other boards (e.g. AX55 v1 uses it). No regression assessment exists, and the family D logic was developed without hardware. Upstream acceptance is not assessed. `[SOURCE]`
- R3 The SerDes/PCS patches (`777-07`, `777-08`) rest on reverse engineering of the vendor driver. Whether they bring up a working SGMII trunk is unknown. `[OPEN]`
- R4 Trunk mode and speed (SGMII 1 Gbps, fixed-link on both ends) come from OEM analysis and have not been measured. `[REPORTED]`
- R5 The DTS has no CPU-port tag-protocol property. Earlier design notes mention `realtek,headerless-cpu-port`; whether the driver in this tree needs it for this topology has not been checked. `[REPORTED]`
- R6 The committed DTS differs from earlier design notes (which mention the NSS dtsi include, an NSS memory region, and `tp_data` as an NVMEM MAC source). The committed file is authoritative; the notes need reconciling. `[REPORTED]`
- R9 Without a `02_network` case, the default LAN/WAN interface layout on top of the DSA ports is not defined. Behavior on first boot is untested. `[OPEN]`

**Wi-Fi and addresses**

- R7 Calibration and board data: the hotplug extracts from `0:ART` at fixed offsets taken from OEM analysis, not validated against real ART contents. ART may be erased on some units (e.g. ISP-supplied), in which case this path yields nothing. No AX23-specific board-data package is selected, and whether the generic firmware packages contain a board entry for variant `TP-Link-Archer-AX23-v2` is not established; an earlier inspection of a built rootfs reported only `m3_fw` for QCN6122. Building `board-2.bin` from the OEM `bdwlan.b24` / `bdwlan.b60` is planned, not done. `[REPORTED]`
- R8 The only MAC logic is in the caldata hotplug (`default-mac` minus 1 / minus 2). The DTS has no MAC source, and no `02_network` case assigns LAN/WAN MACs. Resulting behavior is untested. `[OPEN]`

**Install path and boot**

- R10 `sysupgrade` is not supported yet: the board is absent from `platform.sh`, so it would take the generic branch, which does not implement the dual-slot logic (`rootfs`/`rootfs_1`, `tp_boot_idx`) that the AX55 v1 branch has. `sysupgrade` images exist but must not be used on hardware until this is designed. `[VERIFIED]` (S11) / behavior `[OPEN]`
- R11 `0:BOOTCONFIG`, `0:BOOTCONFIG1` and `0:APPSBLENV` are writable in the DTS by design (boot index handling). `ART`, `tp_data`, `radio` are read-only in the DTS, which protects them from the kernel but not from other tools. `[SOURCE]`

**Build and repository hygiene**

- R12 Reproducibility: the images were built with the uncommitted `config-default` change present (its mtime predates the images and the build `.config` shows `PCS_QCA_UNIPHY=y`; consistent with, not proof of) and, per the staged rootfs, without the uncommitted caldata cleanup (S10). `profiles.json` records only `HEAD`. Hardware tests of these images therefore test "HEAD plus local edits", not a committed state.
- R13 The QEMU PL011 serial options live in the shared `qualcommax/config-6.18`, so they affect every qualcommax target, not only the AX23 v2. A backup of the pre-change config is untracked (`config-6.18.bak-qemu-pl011`). `[SOURCE]`
- R14 `HEAD` carries duplicate AX23 v2 blocks in `11-ath11k-caldata` (1.3). A cleanup exists only as an uncommitted edit. Cosmetic: one `DEVICE_DTS` line in `ipq50xx.mk` is indented with spaces instead of a tab. `[SOURCE]`
- R17 The repo root holds large untracked artifacts (images, logs, root-owned core dumps, `.bak` files, a stray `<stdin>.s`). A blanket `git add` would stage them. `HEAD` is detached (no branch points at the checkpoint). `[VERIFIED]`

**Upstream**

- R16 Upstream maintainers have described 256 MB RAM on ipq50xx as a disqualifier for mainline; this tree is a development port against an upstream snapshot (`r37094+1-98b1185d03`), not an upstream-ready change. `[REPORTED]`

## 5. Overall state and next technical milestone

| Area | State |
|---|---|
| Build integration and image generation | Done; builds and produces 4 images (`[VERIFIED]`, S1-S4) |
| DTS to DTB consistency | Statically consistent (`[VERIFIED]`, S5-S6) |
| Boot on the physical device | **Not demonstrated** |
| Switch / Ethernet | **Not demonstrated** (driver patches unproven on hardware) |
| Wi-Fi 2.4 / 5 GHz | **Not demonstrated** (calibration and board data unresolved) |
| Default network config and MAC assignment | **Not implemented** |
| Persistent install / `sysupgrade` / rollback | **Not implemented** |

The port is at the "builds and is statically consistent" stage. The single most important gap
is that nothing has ever executed on the target hardware.

**Next technical milestone - M1: first observed boot, non-persistent.**
Exit criteria: the initramfs image boots on the physical Archer AX23 v2 without writing flash,
and a serial-console capture shows the kernel reaching userspace; the log is saved
(sanitised of MAC addresses and serial numbers) and the image SHA-256 is recorded next to it.
That capture also answers H2 and, if the driver probes, H3 (the switch ID question).

Before M1 (housekeeping that needs no hardware, to be decided by the project owner; not done
by this document): settle which uncommitted edits belong in the tested state, commit them, and
rebuild so that the tested image corresponds to a recorded commit (R12). Console access and an
OEM-NAND backup (H0) are hard prerequisites.

After M1: M2 switch and SGMII link (H3-H5), M3 Wi-Fi (H7-H8), M4 persistence and rollback
(H10, after a `platform.sh` design).

## Appendix A - repository state at review time

```
HEAD: b2ab51c08c (detached)   parent: 98b1185d03
 M target/linux/qualcommax/ipq50xx/base-files/etc/hotplug.d/firmware/11-ath11k-caldata
 M target/linux/qualcommax/ipq50xx/config-default
?? .config.backup-before-ax23
?? <stdin>.s
?? ax23-images-20261015/
?? build.exit
?? build.log
?? core.8
?? core.9
?? kernel_compile.log
?? target/linux/generic/config-6.18.bak-qemu-pl011
?? target/linux/qualcommax/dts/ipq5018-archer-ax23-v2.dts.bak
```

(The DTS in the working tree is identical to `HEAD`. The `.dts.bak` is a separate backup copy of 8,079 bytes; it was not compared here.)

## Appendix B - commands used for the checks in section 2

Run from the repository root; all are read-only (the DTB decompile writes to `/tmp`).

```sh
git status --short; git log -5 --oneline --decorate
git show --stat b2ab51c08c
git diff
(cd ax23-images-20261015 && sha256sum -c sha256sums)
staging_dir/host/bin/mkimage -l ax23-images-20261015/openwrt-qualcommax-ipq50xx-tplink_archer-ax23-v2-initramfs-uImage.itb
D=build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/image-ipq5018-archer-ax23-v2.dtb
sha1sum "$D"
build_dir/target-aarch64_cortex-a53_musl/linux-qualcommax_ipq50xx/linux-6.18.55/scripts/dtc/dtc -I dtb -O dts "$D" > /tmp/ax23-built.dts
git show HEAD:<script> | sh -n ; sh -n <script>
grep -n 'archer-ax23-v2' <caldata script in HEAD / working tree / build_dir/.../root-qualcommax>
grep -rn -i 'ax23' target/linux/qualcommax/ipq50xx/base-files/{etc/board.d,lib/upgrade}
```
