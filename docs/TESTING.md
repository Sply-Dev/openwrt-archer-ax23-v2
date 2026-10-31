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
| Switch patches present | All eight `777-0x` patches are applied and their keywords appear in the compiled driver source |
| Missing integration points | `02_network`, `01_leds`, and `platform.sh` have **no** AX23 v2-specific case yet — these default to generic fallback behavior, untested |

**None of these confirm the hardware works.** They confirm the build is internally
consistent and matches what was intended, which is a precondition for a hardware test
being meaningful — not a substitute for one.

## Hardware tests — planned, not yet run

Full list with pass criteria in `archer-ax23-v2-port-status.md` section 3 (tests
H0–H9+). Ground rules for all of them: **no firmware is written to the router without
explicit authorization**, and the early tests are planned as non-persistent procedures
(attempting to boot from RAM over UART/TFTP rather than flashing NAND, contingent on
test H0 confirming that OEM U-Boot accepts interactive commands and network loading).

Recommended order, since each depends on the previous one succeeding:

1. **H0 — Preconditions.** Confirm UART console access works at all (the OEM U-Boot
   accepting console input / loading an image over the network is not yet
   established — see `HARDWARE.md` for the UART pinout). Have a NAND backup and
   recovery plan ready before anything else.
2. **H1 — Non-persistent boot.** Load `initramfs-uImage.itb` over UART/TFTP without
   touching NAND. Pass criterion: kernel starts, serial console produces output at
   115200 baud, userspace is reached.
3. **H2 — Kernel log review.** With H1 working, check that NAND partitions match the
   table in `HARDWARE.md`, no kernel oops/panic, and the Ethernet subsystem
   (ESS/UNIPHY) initializes without error.
4. **H3 — Switch detection.** Confirm `rtl8365mb` reports chip ID `0x6642` / chip
   revision `0x0010` and registers the `wan`/`lan1`–`lan4`/`cpu` ports, and ideally
   captures the driver's own probe message (`"found an RTL8367S-VB switch"` vs
   `"found an RTL8367S switch"`). Static analysis (two independent lines of
   evidence, see `docs/RESEARCH.md` and `docs/KNOWN-ISSUES.md` §1) has already
   identified this chip as RTL8367S-VB, "family D", resolving the earlier `0x6642`
   vs `0x6367` identification question. What H3 still needs to confirm is that this
   holds on the physical unit, not just in the vendor firmware's own driver, and
   that the switch is actually reachable and functional over MDIO on real hardware,
   not just correctly identified in theory.
5. **H4 and beyond** — see `archer-ax23-v2-port-status.md` for the rest of the
   sequence (traffic validation per port, radio bring-up, LED/button checks, MAC
   address verification against `KNOWN-ISSUES.md` §3, sysupgrade round-trip).

## If you're reproducing this and have hardware

If you get further than H0 on a physical unit, the single most useful thing you can
report back is **raw console output**, not a summary — paste the actual boot log. Most
of the open questions in `KNOWN-ISSUES.md` (switch chip revision, MAC offset, LED
polarity) are resolved by reading specific lines out of a real boot log or a UART
session, not by re-deriving them from the vendor firmware.

If something fails, the static verification table above tells you what's already been
double-checked on the build side — if a failure doesn't match anything in that list,
it's new information, not a known gap.
