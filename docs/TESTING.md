# Testing status

> **Hardware validation status (through v0.4-3, 2026-11-15):** The OpenWrt port has been
> successfully tested and validated on physical hardware (Archer AX21 v5 identifying as
> AX23 v2 hardware) across multiple iterative releases via U-Boot TFTP RAM boots.
> Ethernet switch 2.5G trunk, `br-lan` bridge forwarding, LED polarity and activity
> triggers, direct WAN connectivity, and automated factory MAC address retrieval are
> fully validated on physical hardware.

The [`archer-ax23-v2-port-status.md`](archer-ax23-v2-port-status.md) file contains
historical review snapshots; this document tracks the active hardware validation log.

## Validation matrix

| Component / Function | Status | Evidence / Release |
|---|---|---|
| U-Boot TFTP RAM Boot | `[VERIFIED]` | Clean bootm execution from RAM; reached shell (v0.2–v0.4-3) |
| Switch Discovery & CPU Trunk | `[VERIFIED]` | RTL8367S-VB probed; 2500base-x link up at 2.5 Gbps Full Duplex with flow control |
| LAN Switch Bridge (`br-lan`) | `[REPORTED]` | Ports lan1–lan4 assigned to `br-lan`; LAN-to-LAN forwarding confirmed with PC (v0.3) |
| LED Polarity | `[REPORTED]` | All 7 LEDs confirmed `GPIO_ACTIVE_HIGH`; remain off at boot and light on state (v0.4) |
| LAN/WAN LED Activity Triggers | `[REPORTED]` | LAN LED blinks with traffic; WAN LED illuminates upon physical link (v0.4-2) |
| Direct WAN Connectivity | `[REPORTED]` | WAN negotiated 1Gbps/Full; ICMP ping to 1.1.1.1 successful from router with 0% loss (v0.4-2 / v0.4-3) |
| Factory MAC Assignment | `[REPORTED]` | `tp_data` mounts automatically at preinit; factory MAC read from `default-mac` populates `br-lan` and `wan` (v0.4-3) |
| LAN Client NAT Forwarding | `[OPEN]` | Direct router ping verified; forwarding client packets across LAN to WAN via NAT pending |
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

## Remaining validation items

### 1. Client LAN-to-WAN routing and NAT forwarding
While direct WAN connectivity from the router itself is verified, client routing requires:
- Connecting a client PC to a LAN port (with static IP or DHCP).
- Executing `ping 1.1.1.1` and HTTP/HTTPS requests from the client machine.
- Verifying iptables/nftables MASQUERADE rules forward and translate traffic across the switch.

### 2. Wi-Fi radio bring-up (`ath11k`)
- While caldata extraction offsets (`0x1000` for IPQ5018 and `0x26800` for QCN6122 in `0:ART`) have been verified bit-for-bit against hardware dumps, the ath11k driver fails to fetch board data with error `-12`.
- Investigation of the `board-2.bin` variant lookup string and board ID is needed.

### 3. Switch calibration (v0.5 target)
- Evaluate newer patch revisions of the RTL8367S-VB family D series to optimize throughput, stability, and SerDes eye calibration.

### 4. Persistent NAND installation
- Flash installation remains unauthorized until dual-boot A/B slot selection (`fw_setenv tp_boot_idx`) is implemented in `platform.sh` and verified safe against bricking.
- All testing must continue using RAM-only TFTP boots (`initramfs-uImage.itb`).
