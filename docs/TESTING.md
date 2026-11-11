# Testing status

> **Hardware result (v0.2, 2026-11-10):** Two PuTTY sessions show U-Boot console
> access, TFTP loading of an initramfs FIT, kernel startup and an OpenWrt shell on
> a physical AX23 v2. These are v0.2 tests. The v0.3 test image has been built,
> but no v0.3 hardware result is recorded here.

The [`archer-ax23-v2-port-status.md`](archer-ax23-v2-port-status.md) file is a
dated 2026-10-17 snapshot. Its post-snapshot updates record later results;
the original audit is retained for historical context.

## Validation stages

| Stage | v0.2 evidence |
|---|---|
| Root access to OEM firmware | Obtained separately for OEM runtime inspection; it does not establish OpenWrt operation |
| Interactive U-Boot and image loading | Serial logs show command access, TFTP transfer and `bootm` execution |
| OpenWrt kernel and userspace | Linux 6.18.55 started and reached `root@OpenWrt:~#` from initramfs |
| Switch discovery and CPU link | Driver reports RTL8367S-VB and DSA ports; GMAC and switch report fixed 2500base-x link up, 2.5 Gbit/s full duplex with RX/TX flow control reported |
| External ports and traffic | `lan1` returned carrier 1 after `ip link set lan1 up`; the other four ports returned 0 in that sequence. No per-port traffic, DHCP, VLAN or sustained forwarding result was supplied |
| Wi-Fi | Deliberately not configured for these tests. Board-data loading failed in the logs; the cause and radio compatibility remain untested |
| v0.3 and persistent installation | v0.3 image built, hardware result pending. No `sysupgrade` or A/B rollback validation follows from the v0.2 RAM boot |

The owner-provided v0.2 PuTTY logs include these representative lines.
The full logs are not included in this public repository because they
contain device identifiers:

```text
rtl8365mb-mdio 90000.mdio-1:1d: found an RTL8367S-VB switch
rtl8365mb-mdio 90000.mdio-1:1d: Link is Up - 2.5Gbps/Full - flow control rx/tx
ipq5018-gmac-dwmac 39d00000.ethernet eth0: Link is Up - 2.5Gbps/Full - flow control rx/tx
br-lan: port 1(eth0) entered forwarding state
OpenWrt SNAPSHOT, r37094+2-98b1185d03
```

The `br-lan` line names `eth0`, but the log alone does not show the full
generated network configuration. That must be inspected in v0.3.

Before the ports were administratively enabled, reading their `carrier` entries
returned `Invalid argument`. The test image did not contain `ethtool`. The later
`carrier` values do not establish why the other ports read 0, or that `lan1`
forwarded packets.

Patch `0002` adds the AX23 v2 case in `board.d/02_network` for LAN/WAN default
roles. It was added after these v0.2 logs. These tests therefore do not show
whether it corrected the default bridge or the inconsistent external link
behavior. It does not modify the DSA driver or PHY link logic.

A QEMU boot of the initramfs, if performed, exercises generic kernel/userspace
only; QEMU's `virt` machine does not emulate the IPQ5018, RTL8367, NAND or radios.

## Static verification already done

The first four rows summarize the 2026-10-17 snapshot in
`archer-ax23-v2-port-status.md` section 2. Later integration changes
are identified separately:

| Check | What it confirmed |
|---|---|
| DTB consistency | The compiled DTB matches the source DTS byte-for-byte in the relevant nodes (switch, radios, boot args) |
| Partition table | The 16 NAND partitions in the DTS are contiguous, no gaps/overlaps, sized consistently with the image size config |
| Kernel configuration | The switch driver and its dependencies (`NET_DSA_REALTEK*`, `PCS_QCA_UNIPHY`) are enabled and built in |
| Switch patches present | The 2026-10-17 snapshot reviewed eight v1 patches. The tree later moved to the project's ten-patch pre-v7/v7 series. The v0.2 logs are separate hardware evidence |
| Integration points | Patch `0002` now adds the `02_network` case, after the v0.2 tests. Board-specific LED setup and `platform.sh` upgrade handling are still absent |

These static checks apply to the build tree reviewed at the time. The v0.2 serial
logs provide separate hardware evidence; neither set of checks validates
persistent installation or complete peripheral operation.

## Remaining validation

For v0.3, record the tested image hash and the source revision alongside a new
serial log. Then check the generated `/etc/config/network` and `br-lan` members to
verify the `02_network` default roles. Test each physical LAN and WAN port with
known cable placement, link state, packet exchange, addressing and repeated
up/down cycles. Capture switch and GMAC errors during sustained traffic. These
checks are needed before attributing any improvement to patch `0002`.

The 2.5 Gbit/s CPU link reported by the v0.2 log is evidence of link bring-up
under OpenWrt. The reported RX/TX flow-control setting is not a measurement of
pause frames or throughput through a physical port. Wi-Fi, LEDs, buttons, MAC
assignment, persistence and rollback require separate tests when they enter
scope. Wi-Fi was intentionally omitted from the v0.2 test plan.

Persistent installation needs a board-specific upgrade design and independent
validation of slot selection and recovery. A successful initramfs boot does not
authorize use of the current `factory` or `sysupgrade` images for NAND installation.
