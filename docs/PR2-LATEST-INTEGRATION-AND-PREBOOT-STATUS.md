# PR #2 — integration and independent preboot status update (2026-11-22)

**For review by Sply-Dev.** This document accompanies [Draft PR #2](https://github.com/Sply-Dev/openwrt-archer-ax23-v2/pull/2), not a claim of hardware validation or merge readiness.

## 1. Proposed patches and integration result

Seven wrapper patches `0006`–`0012` are proposed to reduce ath11k host memory pressure, improve allocation/error-path cleanup and coordinate IPQ5018 Q6 root/user-PD recovery. They do **not** modify Sply's Ethernet, DTS, GPIO map, OEM calibration, or NAND installation scheme.

- All seven wrappers passed `git apply --check` and applied in documented order against pinned OpenWrt `98b1185d039344553aaf8270d0661cfad4f0a54d` (kernel 6.18.55, backports 7.2).
- In a separate, isolated and cache-assisted target checkout, kernel and `package/kernel/mac80211` preparation **and compilation passed**. The built AArch64 `qcom_q6v5_mpd.o` contains `q6_wcss_recover_userpds`; ath11k `dp.o`, `dp_tx.o`, `dp_rx.o` and `ath11k.ko` were produced.
- The focused ath11k DMA setup/cleanup model, eight Q6 recovery models and 13 Python host tests passed.
- The first mac80211 attempt failed before mac80211 compilation because copied host-apk staging metadata retained stale includes. It was corrected only in the isolated build tree; retry passed.
- Some **pre-existing Sply baseline setup patches** required context fuzz or offsets. The seven PR patches themselves applied cleanly.

This **does not constitute a full firmware build**, hardware DMA/concurrency safety proof, real radio initialization or validation that board-file fetch `-12` is resolved. See [docs/BUILD.md](BUILD.md) and [docs/CONTRIBUTION-INVENTORY.md](CONTRIBUTION-INVENTORY.md).

**Important correction:** The original PR description says *no target build of this fork branch was run*. That statement predates the incremental kernel/mac80211 compilation above. We attempted to update the PR description and post a GitHub comment, but the authenticated integration returned **HTTP 403 (Resource not accessible by integration)** for both operations. This branch document is the current, verifiable update.

## 2. New standalone first-boot findings — outside this PR

On the **independent** RAM-only AX23 EU V2.0 firmware project, a source-level review found the first-boot instructions used `init=/bin/sh`, which does not reliably supersede the initramfs `/init`. The correct guard is `rdinit=/bin/sh`. The standalone documentation and tests were corrected on dev at `9b4f39fbad88b043ddb7b62b5f17256333a029a8`, with no rebuild or hardware operation.

A separate reviewed source discrepancy remains: OEM bootloader and vendor switch code identify **GPIO26** for RTL8367 reset, whereas the standalone compiled DTS currently drives **GPIO39** active-low for 25 ms. The actual board's GPIO39 electrical ownership is **unmeasured**. Exact shipped U-Boot RAM/LMB/FIT behavior and verified 1.8 V UART pinout are likewise unknown on our particular unit. Therefore **NO-GO for the standalone image's first bootm** until the passive GPIO electrical and UART/U-Boot checks pass. Source-level deductions from GPL U-Boot are not physical measurements.

This paragraph **does not imply a safety failure was demonstrated on Sply's board** and does not request or include a change to Sply's already hardware-tested DTS or reset assignment. A separately prepared Windows receive-only UART logging utility has **not** been connected to the router and does not substitute for electrical measurements.

See the source-backed [standalone first-boot gate](https://github.com/john35413/openwrt-archer-ax23-v2-build/blob/dev/reports/FINAL_PREBOOT_GATE.md) and [latest contribution report](https://github.com/john35413/openwrt-archer-ax23-v2-build/blob/dev/reports/UPSTREAM-CONTRIBUTION-STATUS-2026-11-22.md).

## 3. Request for community review

We would appreciate Sply's review of the proposed ath11k/Q6 patch ordering, any observed QMI/BDF or Q6 behavior on physical hardware, and any directly measured GPIO26/39 or U-Boot details. Please retain the Draft PR until its relevant hardware testing and maintainer review are complete.

No device was flashed, no proprietary board data/ART/calibration was uploaded, and neither the original upstream repository nor the independent standalone firmware artifacts were changed by this documentation update.
