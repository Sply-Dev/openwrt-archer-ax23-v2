# Testing status

> **No functional boot on a physical TP-Link Archer AX23 v2 has been demonstrated.**
> Everything below this line is either a static check against the build tree and
> vendor firmware, or a planned hardware test that has not been run yet. Treat
> anything not explicitly marked as run-on-real-hardware as unvalidated.

The authoritative, evidence-tagged source for this is
[`archer-ax23-v2-port-status.md`](archer-ax23-v2-port-status.md), which should be
treated as the primary document — this file is a navigation aid on top of it, written
to make "what's actually been checked" and "what to test next, in what order" easier
to find quickly. If the two ever disagree, `archer-ax23-v2-port-status.md` is correct.

## No UART for this project — permanent constraint, not a pending item

This project has no UART/level-shifter hardware for this device and no planned
purchase, a financial constraint rather than a prioritization choice (see
`KNOWN-ISSUES.md` §12). This shapes every test plan below: tests that assume serial
console access (H0–H2 as originally scoped) are blocked indefinitely from this
project's own side, not "not yet done." They remain here as the correct procedure
for **anyone with physical UART access** who wants to test this port, this
project's own route forward is the no-UART path described under each test below
and in "If you have hardware but no UART" at the end of this document.

## What "tested" means in this repository

Two different things get called "testing" in this project, and they are not
interchangeable:

1. **Static verification** — checking that the build tree, compiled artifacts, and
   vendor firmware are internally consistent (e.g. "does the compiled DTB match the
   source DTS", "do the NAND partition offsets add up without gaps"). This catches
   mistakes before they reach hardware. It does **not** prove the hardware will work.
2. **Hardware validation** — actually running something on a physical AX23 v2 and
   observing the result. This is the only kind of test that validates the port. None
   has been performed yet.

A QEMU boot of the initramfs image (see `BUILD.md`) falls into neither category
cleanly: it exercises the generic kernel/userspace, but QEMU's `virt` machine does not
emulate the IPQ5018 SoC, the RTL8367 switch, the NAND flash, or either radio. A
successful QEMU boot is a useful smoke test for userspace breakage; it says nothing
about whether this port works on the real board.

## Static verification already done

Summarized from `archer-ax23-v2-port-status.md` section 2 (full detail and exact
commands there):

| Check | What it confirmed |
|---|---|
| DTB consistency | The compiled DTB matches the source DTS byte-for-byte in the relevant nodes (switch, radios, boot args) |
| Partition table | The 16 NAND partitions in the DTS are contiguous, no gaps/overlaps, sized consistently with the image size config |
| Kernel configuration | The switch driver and its dependencies (`NET_DSA_REALTEK*`, `PCS_QCA_UNIPHY`) are enabled and built in |
| Switch patches present | All 10 `777-0x` patches (pre-v7 revision, see `KNOWN-ISSUES.md` §8) are applied and their keywords appear in the compiled driver source; kernel compiles cleanly with no driver-specific warnings |
| Missing integration points | `02_network`, `01_leds`, and `platform.sh` have **no** AX23 v2-specific case yet — these default to generic fallback behavior, untested |

**None of these confirm the hardware works.** They confirm the build is internally
consistent and matches what was intended, which is a precondition for a hardware test
being meaningful — not a substitute for one.

## Hardware tests — planned, not yet run

Full list with pass criteria in `archer-ax23-v2-port-status.md` section 3 (tests
H0–H9+). Ground rules for all of them: **no firmware is written to the router without
explicit authorization**, and tests that involve flashing are planned to go through
the confirmed A/B mechanism (`fw_setenv tp_boot_idx`, writing the inactive
`rootfs`/`rootfs_1` slot, see `KNOWN-ISSUES.md` §9 and `HARDWARE.md`), which gives a
safe fallback to the current working slot if the new image fails to boot.

Recommended order, since each depends on the previous one succeeding. Each entry
notes whether it needs UART or can be done over the network only.

1. **H0 — Preconditions.** *Needs UART.* Confirm UART console access works at all
   (the OEM U-Boot accepting console input / loading an image over the network is
   not yet established — see `HARDWARE.md` for the UART pinout). Have a NAND
   backup and recovery plan ready before anything else. This project has no UART;
   this test can only be run by a volunteer with physical serial access.
2. **H1 — Non-persistent boot.** *Needs UART* (as scoped) — *or* an equivalent
   network-only signal, see "No-UART path" below. Load `initramfs-uImage.itb` over
   UART/TFTP without touching NAND. Pass criterion: kernel starts, serial console
   produces output at 115200 baud, userspace is reached.
3. **H2 — Kernel log review.** *Needs UART.* With H1 working, check that NAND
   partitions match the table in `HARDWARE.md`, no kernel oops/panic, and the
   Ethernet subsystem (ESS/UNIPHY) initializes without error. This specifically
   includes confirming the **HSGMII 2.5G link mode** (`KNOWN-ISSUES.md` §4) is
   what the kernel actually negotiates, the single most useful boot-log detail
   for anyone with UART to capture and report.
4. **H3 — Switch detection.** Confirm `rtl8365mb` reports chip ID `0x6642` / chip
   revision `0x0010` and registers the `wan`/`lan1`–`lan4`/`cpu` ports, and ideally
   captures the driver's own probe message (`"found an RTL8367S-VB switch"` vs
   `"found an RTL8367S switch"`). Static analysis (two independent lines of
   evidence, see `docs/RESEARCH.md` and `docs/KNOWN-ISSUES.md` §1) has already
   identified this chip as RTL8367S-VB, "family D", resolving the earlier `0x6642`
   vs `0x6367` identification question. What H3 still needs to confirm is that this
   holds on the physical unit, not just in the vendor firmware's own driver, and
   that the switch is actually reachable and functional over MDIO on real hardware,
   not just correctly identified in theory. *Needs UART* for the probe message;
   functional reachability (DHCP lease / ping on a LAN port) is also visible
   without UART, see below.
5. **H4 and beyond** — see `archer-ax23-v2-port-status.md` for the rest of the
   sequence (traffic validation per port, radio bring-up, LED/button checks, MAC
   address verification against `KNOWN-ISSUES.md` §3, sysupgrade round-trip).

### No-UART path: what this project can actually verify without serial access

Since this project has no UART (and no plan to acquire one), the practical test
available to a volunteer tester without serial access is a **sysupgrade attempt
plus network-level observation**, not the H0–H2 sequence above as written. This is
weaker evidence than a boot log (it cannot distinguish "didn't boot" from "booted
but didn't bring up the network the way expected"), but it is the only option
available without a physical UART connection:

- Flash via sysupgrade to the inactive slot, following the A/B mechanism in
  `KNOWN-ISSUES.md` §9.
- Run continuous `ping`/`arping` against the router's expected LAN address
  starting just before power-on/reboot. If OpenWrt boots and brings up the
  HSGMII trunk and at least one LAN port, ICMP should respond before SSH would
  even be reachable.
- If there is no response within a reasonable window and the A/B fallback
  (`KNOWN-ISSUES.md` §9, confirmed mechanism) kicks in, the router should return
  to the previous working slot and respond on its old address — this is itself a
  signal (a failed boot was caught and recovered automatically), not a successful
  test, but it rules out a bricked unit.
- **Known gap, accepted:** a silent failure on both slots (neither new image nor
  fallback responding) has no diagnosis path without UART. This is treated as an
  explicit abort criterion rather than an open mystery to keep investigating
  blind — if it happens, the next step is TFTP recovery via the bootloader if it
  still responds, not further network-level guessing.

This path can confirm or refute the HSGMII link mode indirectly (no network
response at all, versus a response once pause/link settle, versus a confirmed-good
fallback), but cannot substitute for a UART-based H2/H3 capture. Anyone able to
test with actual serial access should prefer the H0–H2 sequence above and report
the raw boot log, see "If you're reproducing this and have hardware" below.

## If you're reproducing this and have hardware

If you get further than H0 on a physical unit, the single most useful thing you can
report back is **raw console output**, not a summary — paste the actual boot log. Most
of the open questions in `KNOWN-ISSUES.md` (switch link mode, chip revision, MAC
offset, LED polarity) are resolved by reading specific lines out of a real boot log
or a UART session, not by re-deriving them from the vendor firmware. The HSGMII vs
SGMII link mode (`KNOWN-ISSUES.md` §4) is the single highest-value thing a boot log
can resolve right now.

If something fails, the static verification table above tells you what's already been
double-checked on the build side — if a failure doesn't match anything in that list,
it's new information, not a known gap.

## If you have hardware but no UART

Follow the "No-UART path" section above. Report what you tried, what responded and
when, and whether the A/B fallback engaged — even an inconclusive result (e.g. "no
response from either slot, had to TFTP-recover") is useful information for this
project, since it is otherwise completely blind to this failure mode.
