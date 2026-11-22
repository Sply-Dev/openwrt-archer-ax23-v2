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

## 2. ath11k / Q6 calibration and board data

`[OPEN]` Wi-Fi compatibility was outside early testing scope.
Calibration data offsets in `0:ART` (`0x1000` for the IPQ5018 2.4 GHz radio, and
`0x26800` for the QCN6122 5 GHz radio, 128KB each) were confirmed bit-for-bit
against raw hardware partition dumps and OEM scripts (`/lib/read_caldata_to_fs.sh`).
However, during kernel boot the `ath11k` driver fails to fetch board data
(QMI board file error `-12`, `failed to fetch board-2.bin`). The exact root cause
of the board-file mismatch remains to be investigated.

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
