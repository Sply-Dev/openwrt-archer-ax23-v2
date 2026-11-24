# Known issues, open questions, and licensing notes

Evidence tags used throughout this file, consistent with
[`archer-ax23-v2-port-status.md`](archer-ax23-v2-port-status.md):

| Tag | Meaning |
|---|---|
| `[VERIFIED]` | Checked by a command whose output is shown or linked. |
| `[SOURCE]` | Read directly from a file in this tree or a vendor-supplied archive. |
| `[REPORTED]` | Confirmed by a third party with physical UART access to the device (see Credits). |
| `[OPEN]` | Unknown, or a hypothesis not yet tested. |

## 1. Switch chip identification (family D)

`[VERIFIED]` by static analysis and runtime MDIO probe on physical hardware. The Ethernet switch
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

**Hardware confirmation:** The `rtl8365mb` driver probes and identifies the switch
over MDIO as `RTL8367S-VB` on physical hardware boots (v0.2 through v0.4-3).

## 2. ath11k / Q6 calibration, board data (`-12`), and regdomain handling

**Status:** `[VERIFIED]` root cause of the `-12` board-file error and `ath11k_remove_regdomain` corruption proven by rootfs/kernel source trace and byte-level inspection of physical `0:ART` dumps (`v0.6-wifi-integration`); `[OPEN]` physical hardware boot of the integrated `v0.6-wifi-integration` image to confirm dual-radio initialization and RF performance.

### 2.1. Root cause of the QMI board-file fetch `-12` (`-ENOMEM`) error (`[VERIFIED]`)

In builds v0.1 through v0.5, both radios reached the QMI board-data request stage during boot and failed with `failed to fetch board-2.bin` / `qmi failed to fetch board file: -12`. Tracing the compiled `root-qualcommax` filesystem and kernel 6.18 firmware-loader path confirms this was **not** a RAM allocation shortage:

1. **No `board-2.bin` was installed in the rootfs:** `target/linux/qualcommax/image/ipq50xx.mk` only listed `ath11k-firmware-ipq5018-qcn6122` (which installs `q6_fw.*` and `m3_fw.*`), with no `ipq-wifi-*` package for `tplink_archer-ax23-v2`. Consequently, `/lib/firmware/ath11k/IPQ5018/hw1.0/board-2.bin` and `/lib/firmware/ath11k/QCN6122/hw1.0/board-2.bin` were physically absent from the image.
2. **Why a missing file returns `-12` (`-ENOMEM`) instead of `-2` (`-ENOENT`):** When `ath11k_core_fetch_board_data_api_n()` calls `firmware_request_nowarn()`, the missing file triggers the kernel's sysfs user-helper fallback (`CONFIG_FW_LOADER_USER_HELPER_FALLBACK=y`, `CONFIG_FW_LOADER_PAGED_BUF=y`). OpenWrt's `procd` (`plug/hotplug.c: handle_firmware()`) sees `stat()` fail and immediately writes `loading=1` followed by `loading=0` with zero data bytes. In Linux 6.18 (`drivers/base/firmware_loader/fallback.c:127-131`), closing a paged firmware buffer with zero bytes returns `-ENOMEM` (`-12`):
   ```c
   else if (fw_priv->is_paged_buf && !fw_priv->data)
       retval = -ENOMEM;
   ```
3. **Selector format and TLV structure required by `ath11k` (`core.c`):**
   - From the OEM FIT DTB (`ax23-oem-fit.dts`), the vendor QSDK `cnss2` driver defines `qcom,board_id = <0x24>` (decimal `36`) for IPQ5018 and `qcom,board_id = <0x60>` (decimal `96`) for QCN6122. In contrast, OpenWrt's `ath11k` queries the silicon OTP `board_id` over QMI (`255` / `0xff` when unprogrammed) and formats the lookup string in decimal (`qmi-board-id=%d`).
   - `ath11k_core_parse_bd_ie_board()` requires a 20-byte padded header (`"QCA-ATH11K-BOARD\0\0\0\0"`), unpadded `strlen(boardname)` in `ATH11K_BD_IE_BOARD_NAME`, and **one separate outer `ATH11K_BD_IE_BOARD` TLV per selector name** (because the parser executes `goto out;` on the first `ATH11K_BD_IE_BOARD_NAME` mismatch inside an outer IE).
   - **Resolution in `v0.6-wifi-integration`:** Patch `0015` adds `package/firmware/ipq-wifi-tplink-archer-ax23-v2` to `DEVICE_PACKAGES`, and `board2-builder-fixed.py` packages the 128 KiB BDFs into validated `board-2.bin` containers covering both `qmi-board-id=255` and `qmi-board-id=36` (IPQ5018) / `96` (QCN6122).

### 2.2. Factory `0:ART` calibration vs. OEM rootfs `bdwlan.b24`/`b60`, and why `ath11k_remove_regdomain` must not run (`[VERIFIED]`)

Calibration data offsets in `0:ART` (`0x1000` for the IPQ5018 2.4 GHz radio, and `0x26800` for the QCN6122 5 GHz radio, 131,072 bytes each) were confirmed bit-for-bit against raw hardware partition dumps (`bdf-ipq5018-unit.bin`, `bdf-qcn6122-unit.bin`) and the OEM script `/lib/read_caldata_to_fs.sh` (`ap-mp02.1*` case).

Byte-by-byte comparison between the physical `0:ART` slices and the OEM rootfs regional board files (`EU/00000001/lib/firmware/IPQ5018/WIFI_FW/bdwlan.b24` and `qcn6122/bdwlan.b60`) established two critical facts:

1. **Per-unit factory RF calibration resides in `0:ART`:** Exactly 25 bytes on 2.4 GHz (`0x000a..0x000b` checksum + 23 bytes in `0x01a00..0x01a1a`, `0x0e25b..0x0e26d`, `0x106f0`) and 93 bytes on 5 GHz (84 bytes against the `TW` variant) are populated with unit-specific calibration values in `0:ART` where the generic `bdwlan.b24`/`b60` templates in the stock squashfs are zeroed (`0x00`) or uncalibrated.
2. **Offset `0x34` is already `0x0000` from the factory, while `0x458` and `0x5a8` hold non-regdomain BDF data:** Inspecting the five candidate offsets touched by OpenWrt's `ath11k_remove_regdomain()` (`package/base-files/files/lib/functions/caldata.sh`) across all regional `bdwlan` files and the physical `0:ART` dumps yields:
   ```text
   EU bdwlan.b24 / unit 2.4G 0:ART : 0x034=0000  0x450=0000  0x458=aff9  0x500=0000  0x5a8=0000
   EU bdwlan.b60 / unit 5G   0:ART : 0x034=0000  0x450=0000  0x458=0000  0x500=0000  0x5a8=00e1
   ```
   - In unpatched OpenWrt, calling `ath11k_remove_regdomain` without a `$target` argument caused `hexdump` to read empty `stdin`, matching `"" == ""` on all four loop offsets and overwriting `0x458` (`0xaff9` -> `0x0000` on 2.4 GHz) and `0x5a8` (`0x00e1` -> `0x0000` on 5 GHz) while corrupting the BDF checksum at `0x0a`.
   - Furthermore, the OEM `/lib/read_caldata_to_fs.sh` script extracts `0:ART` at `+4096` (`0x1000`) and `+157696` (`0x26800`) directly with `dd` and never zeroes any regdomain offset.
   - **Resolution in `v0.6-wifi-integration`:** Patch `0001` (`11-ath11k-caldata`) no longer calls `ath11k_remove_regdomain` on `tplink,archer-ax23-v2`, and patch `0014` fixes the missing default `$target` in `caldata.sh`.

### 2.3. Live OEM firmware Wi-Fi baseline from physical hardware (`[VERIFIED]`)

Direct shell inspection (`dmesg` and `iwconfig ath0 ath1`) on a physical Archer AX23 v2 running stock firmware confirms the reference behavior that `v0.6-wifi-integration` matches:

1. **MAC derivation (`label_mac - 1` / `label_mac - 2`) and radio initialization order:**
   - Base label MAC (`tp_data/default-mac`): `EC:B9:31:xx:xx:54` (default SSID suffix `_B854`).
   - `ath0` (IPQ5018 2.4 GHz, `802.11axg`, `hw_mode: 29`): initializes first (`~45.4 s`), assigned MAC `EC:B9:31:xx:xx:53` (`label_mac - 1`), `Setting Max Stations: 128` (matching `fw_mem_mode = 2`).
   - `ath1` (QCN6122 5 GHz, `802.11axa`, `hw_mode: 30`): initializes second (`~50.3 s`), assigned MAC `EC:B9:31:xx:xx:52` (`label_mac - 2`), `Setting Max Stations: 128`.
2. **Stock driver confirmation that `0x34` regdomain is `0x0000` in BDF/ART:**
   - On both radios, the stock QCA driver logs:
     ```text
     ol_ath_ucfg_setparam: Unable to set regdomain, restore orig_rd = 22
     wlan_cfg80211_set_country: Country: US ret: 0
     ```
     confirming that the raw BDF/ART carries `0x0000` at offset `0x34` and the regulatory domain is applied via `cfg80211` country code at runtime.
3. **Reference TX power and BDF noise floor (`iwconfig ath0` / `iwconfig ath1`):**
   - `ath0` (2.4 GHz, channel 9 / `2.452 GHz`, HE40 `573.5 Mb/s`): **`Tx-Power: 24 dBm`**, **`Noise level: -101 dBm (BDF averaged NF value in dBm)`**.
   - `ath1` (5 GHz, channel 149 / `5.745 GHz`, HE80 `1.201 Gb/s`): **`Tx-Power: 26 dBm`**, **`Noise level: -97 dBm (BDF averaged NF value in dBm)`**.
   - These figures provide the exact hardware baseline to verify that `v0.6-wifi-integration` (using the `0:ART`-derived `board-2.bin` files) does not hit the `13 dBm` fallback cap observed when uncalibrated zero-filled `bdwlan` templates are used with `WLAN.HK.2.7.0.1-01744`.

## 3. MAC address origin and U-Boot ART error

**Status:** `[RESOLVED]` by binary disassembly of vendor U-Boot (`appsbl.bin`),
live NAND extraction of `/dev/mtd13` (`tp_data`), OpenWrt implementation (patches `0003` and `0004`),
and physical hardware validation (v0.4-3).

### Why U-Boot logs "eth0 MAC Address from ART is not valid"
Disassembly of `appsbl.bin` (ARM32 / Thumb2, entry `0x4a920000`, caller at `0x4a924604`)
shows that Qualcomm U-Boot unconditionally reads page 0 (`0x0000`) of partition `"0:ART"`
via `ops->read_page` (`0x4a9285ac`) expecting 12 bytes (`eth0` at `+0x0`, `eth1` at `+0x6`).
On TP-Link devices, partition `0:ART` has `0xFF` in `0x0000..0x0630` (unwritten flash).
Validation at `0x4a924636` tests bit 0 of byte 0 (`ldrb r3, [mac]; lsls r2, r3, #31; bmi ...`),
which tests the I/G (Individual/Group multicast) bit. For `0xFF`, bit 0 is 1, causing the branch
to trigger the error string `"eth%d MAC Address from ART is not valid\n"` and generating a
random MAC for Qualcomm driver initialization.
**Conclusion:** ART does not contain the Ethernet MAC on this device. Do not create DTS nvmem cells pointing to ART for GMAC.

### True Factory MAC Location
TP-Link stores factory calibration and device data in an authenticated UBIFS volume on NAND
partition `tp_data` (`/dev/mtd13`).
Inside `tp_data` (file `default-mac`), the factory MAC is stored as 6 raw binary bytes
(e.g., `EC:B9:31:C6:B8:54`, OUI `EC:B9:31` registered to TP-Link Technologies Co.,Ltd.).

### OpenWrt Resolution
1. **Preinit mount (`0004`):** `target/linux/qualcommax/ipq50xx/base-files/lib/preinit/09_mount_tp_data`
   attaches and mounts the `tp_data` volume read-only at `/tmp/tp_data`.
2. **MAC assignment (`0003`):** `target/linux/qualcommax/ipq50xx/base-files/etc/board.d/02_network`
   reads `/tmp/tp_data/default-mac` via `get_mac_binary "/tmp/tp_data/default-mac" 0`, assigning
   the factory MAC to `lan` (`br-lan`) and `macaddr_add "$label_mac" 1` to `wan`.

### Hardware Validation (v0.4-3)
In v0.4-2 testing, preinit mount failed because a leftover `09_mount_tp_data.orig` backup
file was sourced alphabetically after `09_mount_tp_data`, silently redefining the preinit
function without the AX23 v2 board case. This was resolved in v0.4-3. In v0.4-3 hardware
testing, `tp_data` mounted automatically during preinit and both `br-lan` and `wan` came
up with the correct factory MAC matching the router's physical label.

### LED Behavior (LAN & Dual-Color WAN)
- **LAN LED (`white:lan`):** Triggered by `br-lan` activity via `01_leds` (`ucidef_set_led_netdev "lan" "LAN" "white:lan" "br-lan"`).
- **WAN LED (`white:wan`):** Triggered by `wan` link/traffic via `01_leds`.
- **Amber WAN LED (`led-wan-orange`, GPIO12):** Left unconfigured by default, identical to upstream OpenWrt's `tplink,archer-ax55-v1` configuration. In stock firmware, amber indicates physical carrier present without internet connectivity (DHCP lease / DNS unreachable). The Linux kernel `ledtrig-netdev` driver only triggers on physical link/carrier/traffic; application-level conditional coloring requires userspace hotplug scripts, which can be configured post-install if desired.

## 4. Trunk link speed / SGMII vs HSGMII

The project's DTS configures the GMAC1 to switch CPU-port trunk as HSGMII
2.5G (`2500base-x`, fixed-link speed 2500) with `pause` on both fixed-link
nodes. The OpenWrt kernel log reports the switch and GMAC links up at
2.5 Gbit/s, full duplex, with RX/TX flow control reported.

Evidence from the OEM configuration:

- The U-Boot source configures `MODE_EXT_HSGMII` and `PORT_SPEED_2500M` and
  prints `Set RTL8367S SGMII 2.5Gbps`.
- On running stock hardware, UNIPHY/GMAC TX and RX clocks were measured at
  312.5 MHz, consistent with 2500Base-X rather than a 1 Gbit/s link.
- The OEM DTB contains `phy-mode = "sgmii"` on the GMAC side. The
  switch's `port@1` has `forced-speed = <0x9c4>` (2500) and
  `forced-duplex = <1>`. The `phy-mode` string alone does not establish
  a 1 Gbit/s operating speed.

**Hardware validation:** On physical hardware running OpenWrt:
- The CPU link consistently establishes at 2.5 Gbit/s full duplex.
- `br-lan` port membership and LAN-to-LAN packet forwarding were confirmed in v0.3.
- WAN port physical link negotiation (1 Gbps) and external ICMP ping connectivity from the router were confirmed in v0.4-2 / v0.4-3.
- v0.5 (2026-11-20, Veraxis, physical hardware): `[REPORTED]` the trunk locks at 2.56 s
  and stays stable, with 3/3 cold boots and 2/2 soft reboots clean. LAN-to-WAN client
  routing with automatic DHCP works (OpenSpeedTest: 444.95 Mbps down / 100.35 Mbps up;
  the upload figure is ISP-dependent according to the tester).

### Resolved in v0.5: trunk lock timing and UNIPHY preconfiguration

Before v0.5, whether the EXT0/SDS0 trunk would lock reliably on cold boot was
`[OPEN]`. On IPQ5018 the UNIPHY is only programmed to the target mode (`2500base-x`) on
the first `ndo_open` of the Ethernet interface, while the RTL8367S-VB brings up its SerDes
about 2 seconds earlier, during probe, and trains against whatever the bootloader left
behind. Patch `0006` (`qca_uniphy_pcs_preconfig()`, a manual rebase of
openwrt/openwrt#26597 by Johan Alvarado, `c127dev`) programs the UNIPHY at GMAC probe
time. The earlier family C testing of that PR did not cover family D with HSGMII 2.5G;
this result does. The `777-08` re-latch worker remains active as a fallback and was not
tested as an alternative to the preconfig.

The brief `lan1` link bounce seen between 65 s and 73 s is standard Gigabit
auto-negotiation on the RJ45 port combined with the bridge STP delay. It is expected
and does not affect the user.

Optional future work, not a blocker: formal multi-client throughput under load (iperf3).

## 5. LED polarity and physical port mapping

**Status:** `[RESOLVED]` by live OEM device tree inspection, `01_leds` implementation (patch `0005`), and physical hardware validation (v0.4 / v0.4-2).

- **Polarity:** All 7 LED nodes (`power`, `lan`, `wps`, `wlan_2g`, `wlan_5g`, `g_wan`, `o_wan`) were confirmed as `GPIO_ACTIVE_HIGH` from the live OEM device tree (`flags 00 00 00 00`). Testing on physical hardware (v0.4) confirmed that LEDs remain off at boot and only illuminate when active.
- **Triggers:** Network link/activity triggers for LAN (`white:lan` -> `br-lan`) and WAN (`white:wan` -> `wan`) were wired in `board.d/01_leds` and verified working on real hardware in v0.4-2.
- **Port mapping:** Physical LAN ports 1–4 were verified functional under `br-lan` in v0.3.

## 6. Upstream mainline acceptance

`[OPEN]` The Archer AX23 v2 has 256MB of RAM. OpenWrt maintainers have
expressed reluctance to accept devices with 256MB of RAM on modern WiFi 6 targets
into the official tree without careful memory tuning (e.g. `ath11k-fw-memory-mode = 2`,
omitting NSS reservations).

## 7. GPL source completeness: `qca-ssdk` kernel module

`[OPEN]` The vendor GPL archive provides source for most components, but `qca-ssdk`
is delivered as a precompiled binary object in some tarballs. The analysis in this
repository was derived through disassembly of the binary kernel module and
cross-referencing with open drivers.

## 8. Switch driver patch set used in this project (PR #19644)

The ten `rtl8365mb` patches (`777-01` through `777-10`) carried in this repository
are based on OpenWrt PR #19644 (net-next v7). They provide RTL8367S-VB family D
infrastructure, SerDes configuration, and L2 LUT access.

## 8.1. A separate, already-merged series covers the same SerDes path (Johan Alvarado, net-next)

Alvarado's patch series refactored SerDes handling in mainline Linux. The v7 series
carried here implements the appropriate PCS interfaces compatible with that refactoring.

## 8.2. PR #19644's own checklist confirms the gap, and work to close it is already underway upstream

The switch driver author continues to update the series upstream. Migration to newer
patch revisions (e.g. v9/v10 or mainline submissions) is not part of v0.5. v0.5 added
the UNIPHY PCS preconfiguration instead (see section 4); the `777-0x` series is unchanged.

## 8.3. Direct comparison: this tree's `777-07`/`777-08` already implement Alvarado's `phylink_pcs` model for family D

Inspection of the patches confirms that SerDes interface control for family D is
cleanly handled through phylink PCS.

## 9. Boot slot selection mechanism

`[OPEN]` The dual-boot A/B layout uses `fw_setenv tp_boot_idx <0|1>` against the U-Boot
environment partition (`APPSBLENV`). Implementation and testing of `platform.sh`
sysupgrade logic for permanent NAND installation is tracked for future releases.

## 10. `pause` on the GMAC1/CPU-port fixed-link

`[VERIFIED]` by source inspection. The `pause;` property in DTS is honored by the
generic forced-mode path in `rtl8365mb_ext_config_forcemode()`. Physical flow control
under heavy network load remains to be benchmarked.
