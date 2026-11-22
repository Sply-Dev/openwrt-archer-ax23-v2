# Testing status

> **Hardware validation status (through v0.5, 2026-11-20):** The OpenWrt port has been
> successfully tested and validated on physical hardware (Archer AX21 v5 identifying as
> AX23 v2 hardware) across multiple iterative releases via U-Boot TFTP RAM boots.
> Ethernet switch 2.5G trunk (stable across cold boots as of v0.5), `br-lan` bridge
> forwarding, LED polarity and activity triggers, WAN connectivity, LAN-to-WAN client
> routing with DHCP, and automated factory MAC address retrieval are validated on
> physical hardware.

The [`archer-ax23-v2-port-status.md`](archer-ax23-v2-port-status.md) file contains
historical review snapshots; this document tracks the active hardware validation log.

## Validation matrix

| Component / Function | Status | Evidence / Release |
|---|---|---|
| U-Boot TFTP RAM Boot | `[VERIFIED]` | Clean bootm execution from RAM; reached shell (v0.2–v0.4-3) |
| Switch Discovery & CPU Trunk | `[VERIFIED]` | RTL8367S-VB probed; 2500base-x link up at 2.5 Gbps Full Duplex with flow control |
| UNIPHY PCS preconfig, EXT0/SDS0 trunk | `[REPORTED]` | Trunk locked at 2.56 s, stable for the whole test; 3/3 cold boots and 2/2 soft reboots clean. Source: Veraxis, physical hardware, 2026-11-20 (v0.5) |
| LAN Switch Bridge (`br-lan`) | `[REPORTED]` | Ports lan1–lan4 assigned to `br-lan`; LAN-to-LAN forwarding confirmed with PC (v0.3) |
| LED Polarity | `[REPORTED]` | All 7 LEDs confirmed `GPIO_ACTIVE_HIGH`; remain off at boot and light on state (v0.4) |
| LAN/WAN LED Activity Triggers | `[REPORTED]` | LAN LED blinks with traffic; WAN LED illuminates upon physical link (v0.4-2) |
| Direct WAN Connectivity | `[REPORTED]` | WAN negotiated 1Gbps/Full; ICMP ping to 1.1.1.1 successful from router with 0% loss (v0.4-2 / v0.4-3) |
| Factory MAC Assignment | `[REPORTED]` | `tp_data` mounts automatically at preinit; factory MAC read from `default-mac` populates `br-lan` and `wan` (v0.4-3) |
| LAN Client NAT Forwarding | `[REPORTED]` | Automatic DHCP, real web page loads and OpenSpeedTest from a LAN client: 444.95 Mbps down / 100.35 Mbps up, 12.0 ms ping, 1.00 ms jitter. Source: Veraxis, 2026-11-20 (v0.5) |
| Wi-Fi (2.4 GHz & 5 GHz) | `[OPEN]` | Caldata offsets verified against dump; driver blocked on board-data fetch error `-12` |
| Persistent Flash Install | `[OPEN]` | Non-persistent RAM boot only; `platform.sh` dual-boot A/B handling unvalidated |

## Hardware test log by release

### v0.2 (2026-11-10): Initial RAM boot
- U-Boot serial console access verified via UART (115200 8N1, 1.8V).
- Initramfs FIT image loaded via TFTP and executed with `bootm`.
- Linux kernel 6.18.55 booted to an interactive OpenWrt shell.
- RTL8367S-VB switch detected over MDIO; 2.5 Gbps CPU link established.

### v0.3 (2026-11-12): LAN bridge and forwarding
- Patch `0002` applied to configure default interface roles.
- `br-lan` bridge correctly grouped `lan1` through `lan4`.
- A PC connected to physical LAN ports received link, entered forwarding state, and verified bidirectional LAN-to-LAN packet traffic.

### v0.4 (2026-11-13): LED polarity correction
- Corrected all 7 LED nodes from `GPIO_ACTIVE_LOW` to `GPIO_ACTIVE_HIGH` in the DTS based on stock device tree registers (`flags 00 00 00 00`).
- Hardware verification confirmed LEDs stay off upon boot and correctly respond to active events without inverted behavior.

### v0.4-2 (2026-11-14): WAN negotiation, ping, and LED triggers
- Patch `0005` added `netdev` LED triggers for LAN and WAN in `board.d/01_leds`.
- Connecting a PC to LAN caused the LAN LED to illuminate and blink with traffic.
- Connecting an upstream modem/router to WAN caused the white WAN LED to illuminate.
- The WAN interface negotiated 1Gbps/Full link.
- ICMP ping test from the router console (`ping -c 6 1.1.1.1`) passed with 6/6 packets received, 0% loss, ~10ms latency.
- Factory MAC address fell back to U-Boot default (`00:11:22:33:44:56`) due to a preinit mount failure. Manual investigation confirmed `tp_data` held valid data and `default-mac` matched the router's bottom label.

### v0.4-3 (2026-11-15): Preinit mount fix and factory MAC validation
- Root-caused the preinit mount failure: a leftover `09_mount_tp_data.orig` patch backup file was being sourced alphabetically after `09_mount_tp_data`, silently redefining the preinit function without the AX23 v2 case.
- Removed `.orig` and added `.gitignore` rules.
- Hardware verification confirmed that `tp_data` mounts automatically at boot without manual intervention.
- `ip link show br-lan` showed factory MAC `78:20:51:cc:75:78` (matching router label).
- `ip addr show wan` showed factory MAC `78:20:51:cc:75:79` (`base + 1`).
- WAN link negotiation and external ping to 1.1.1.1 were re-verified clean.

### v0.5 (2026-11-20): UNIPHY PCS preconfiguration

Source for every result in this section: Veraxis, physical hardware, 2026-11-20
(OpenWrt forum thread `t/254876`).

**What changed:** patch `0006` adds `qca_uniphy_pcs_preconfig()`, called at GMAC probe
time. It is a manual rebase of openwrt/openwrt#26597 (Johan Alvarado, `c127dev`), which
was previously tested on family C hardware (MR80X v2, AX55 v1, H3C RC3000 v3) and had
not been tested on family D with an HSGMII 2.5G trunk before this project. The family D
re-latch worker (`777-08`) is unchanged and remains active as a fallback; it was not
replaced and not tested as an alternative to the preconfig.

**Why:** on IPQ5018 the UNIPHY is only programmed to the target PHY mode (`2500base-x`
for this device's HSGMII trunk) on the first `ndo_open` of the Ethernet interface. The
RTL8367S-VB brings up its own SerDes about 2 seconds earlier, during probe, and trains
against whatever the bootloader left behind rather than the rate OpenWrt wants.

**Results:** `[REPORTED]` by Veraxis on physical hardware (EXT0/SDS0 trunk). The tester
device is an Archer AX21 v5 (US variant) that identifies as AX23 v2 hardware; the
boot log shows `Machine model: TP-Link Archer AX23 v2` and an RTL8367S-VB switch. This
project has not compared that unit against a retail AX23 v2 board, so the result is
tagged for the tester's unit.
- The 2.5G CPU-to-switch trunk locked at 2.56 s and stayed stable for the whole test.
- 3/3 cold boots (power unplugged) and 2/2 soft reboots were clean. This closes the
  timing race that was the open item of v0.5. Cold boots are historically the main
  problem on IPQ5018 devices, which often fail to synchronize the SerDes.
- LAN-to-WAN works: automatic DHCP, real web page loads, and an OpenSpeedTest run
  (2026-11-20, 9:46 AM EST) of 444.95 Mbps down / 100.35 Mbps up / 12.0 ms ping /
  1.00 ms jitter. The tester's own experience is that 400-500 Mbps is typical for
  IPQ5018 devices without NSS, so the download figure is plausible. The tester does not
  fully trust the upload figure: their ISP upload speed fluctuates with time of day, so
  it reflects the connection rather than the router. The client used automatic DHCP
  from the router for all runs.
- A brief `lan1` link bounce between 65 s and 73 s is standard Gigabit auto-negotiation
  on the physical RJ45 port combined with the bridge STP delay. It is expected
  behavior and does not affect the user.

**Status correction:** the v0.5 entry previously read `[OPEN]` ("not yet validated on
physical hardware"). It is now `[REPORTED]` as described above (third-party hardware result, not a
command run by this project).

**Possible optional future work:** formal multi-client throughput under load (iperf3).
This is not a blocker.

## Remaining validation items

### 1. Wi-Fi radio bring-up (`ath11k`)
- While caldata extraction offsets (`0x1000` for IPQ5018 and `0x26800` for QCN6122 in `0:ART`) have been verified bit-for-bit against hardware dumps, the ath11k driver fails to fetch board data with error `-12`.
- Investigation of the `board-2.bin` variant lookup string and board ID is needed.

### 2. Persistent NAND installation
- Flash installation remains unauthorized until dual-boot A/B slot selection (`fw_setenv tp_boot_idx`) is implemented in `platform.sh` and verified safe against bricking.
- All testing must continue using RAM-only TFTP boots (`initramfs-uImage.itb`).
