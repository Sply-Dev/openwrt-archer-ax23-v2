#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the prepared ath11k_dp_srng_setup()/ath11k_dp_srng_cleanup() against a
page-aligned DMA model (dma-direct: one alloc_pages(get_order(size)) block, no
IOMMU, as on IPQ5018) for the FW-memory-mode-2 ring set of one AX23 radio.

  check_ath11k_ring_alloc.py PATH/ath11k/dp.c [--expect-fail]

Entry sizes are sizeof() of the backports-7.2 HAL descriptors (host-compiled
from hal_desc.h): REO dst 64, WBM release 32, WBM idle link 8, RXDMA buf 8,
REO entrance 32, TCL data 4+28."""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# (name, entry bytes, entries in FW memory mode 2, copies per radio)
RINGS = [
    ("WBM idle link", 8, 32768, 1),
    ("REO destination", 64, 2048, 4),
    ("TX completion (961)", 32, 2048, 1),
    ("RX release", 32, 1024, 1),
    ("RXDMA error destination (962)", 32, 1024, 1),
    ("TCL data", 32, 512, 1),
    ("REO exception", 64, 128, 1),
    ("RXDMA buffer (962)", 8, 1024, 1),
    ("REO status", 104, 2048, 1),
]


def function(src, name):
    m = re.search(r"^(?:static\s+)?(?:int|void)\s+" + name + r"\([^;{]*\)\s*\{", src, re.M)
    if not m:
        raise SystemExit(f"missing driver definition: {name}")
    return src[m.start():src.index("\n}\n", m.end()) + 3]


HEADER = r"""
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
typedef uint32_t u32; typedef uint8_t u8; typedef uint64_t dma_addr_t;
#define GFP_KERNEL 0
#define DMA_FROM_DEVICE 0
#define HAL_RING_BASE_ALIGN 8
#define PTR_ALIGN(p, a) ((void *)(((uintptr_t)(p) + (a) - 1) & ~(uintptr_t)((a) - 1)))
#define IS_ALIGNED(x, a) ((((uintptr_t)(x)) & ((a) - 1)) == 0)
#define WARN_ON_ONCE(c) (c)
#define ath11k_warn(...) ((void)0)
struct dp_srng { u32 *vaddr_unaligned; u32 *vaddr; dma_addr_t paddr_unaligned; dma_addr_t paddr;
                 int size; u32 ring_id; u8 cached; };
struct hal_srng_params { void *ring_base_vaddr; dma_addr_t ring_base_paddr; unsigned long num_entries,
    intr_batch_cntr_thres_entries, intr_timer_thres_us, low_threshold, flags, msi_addr, msi_data; };
struct ath11k_base { void *dev; struct { bool alloc_cacheable_memory; } hw_params; };
static int cur_entry, misalign; static long live_bytes, last_alloc, allocs;
static int order_of(long n) { int o = 0; while ((4096L << o) < n) o++; return o; }
static void *dma_alloc(long size, dma_addr_t *pa) {
    long blk = 4096L << order_of(size);
    char *p = aligned_alloc(4096, blk);
    allocs++; last_alloc = size; live_bytes += blk;
    if (misalign) p += 4;
    *pa = (dma_addr_t)(uintptr_t)p; return p;
}
static void dma_free(long size, void *v) { live_bytes -= 4096L << order_of(size);
    free((void *)((uintptr_t)v & ~(uintptr_t)4095)); }
#define dma_alloc_coherent(d, s, pa, g) dma_alloc((s), (pa))
#define dma_alloc_noncoherent(d, s, pa, dir, g) dma_alloc((s), (pa))
#define dma_free_coherent(d, s, v, pa) dma_free((s), (v))
#define dma_free_noncoherent(d, s, v, pa, dir) dma_free((s), (v))
static int ath11k_hal_srng_get_entrysize(struct ath11k_base *ab, int t) { return cur_entry; }
static int ath11k_hal_srng_get_max_entries(struct ath11k_base *ab, int t) { return 1 << 20; }
static void ath11k_dp_srng_msi_setup(struct ath11k_base *ab, struct hal_srng_params *p, int t, int n) {}
static int ath11k_hal_srng_setup(struct ath11k_base *ab, int t, int r, int m, struct hal_srng_params *p) {
    /* the hardware ring must lie inside the allocation with HAL_RING_BASE_ALIGN */
    if (!IS_ALIGNED(p->ring_base_paddr, HAL_RING_BASE_ALIGN)) return -100;
    return 1; }
"""

MAIN = r"""
struct ring { const char *n; int e, num, copies; };
int main(void) {
    static const struct ring rings[] = { %RINGS% };
    struct ath11k_base ab = {0};
    long total = 0; int fails = 0, max_order = 0;
    for (unsigned i = 0; i < sizeof(rings) / sizeof(rings[0]); i++) {
        struct dp_srng r = {0};
        long need = (long)rings[i].e * rings[i].num;
        cur_entry = rings[i].e;
        int ret = ath11k_dp_srng_setup(&ab, &r, HAL_RXDMA_DST, 0, 0, rings[i].num);
        int ord = order_of(last_alloc), want = order_of(need);
        long blk = (4096L << ord) * rings[i].copies;
        bool ok = !ret && ord == want && (char *)r.vaddr + need <= (char *)r.vaddr_unaligned + (4096L << ord);
        printf("%s ring %-30s %6ld B x%d -> order %d (%ld KiB)\n", ok ? "PASS" : "FAIL",
               rings[i].n, need, rings[i].copies, ord, blk / 1024);
        fails += !ok; total += blk; if (ord > max_order) max_order = ord;
        ath11k_dp_srng_cleanup(&ab, &r);
    }
    printf("INFO ring DMA per radio %ld KiB, highest ring order %d\n", total / 1024, max_order);
    misalign = 1; allocs = 0;
    { struct dp_srng r = {0}; cur_entry = 8;
      int ret = ath11k_dp_srng_setup(&ab, &r, HAL_RXDMA_DST, 0, 0, 1024);
      bool ok = ret != 0 && live_bytes == 0 && !r.vaddr_unaligned;
      printf("%s misaligned allocation refused and freed (ret %d, live %ld)\n", ok ? "PASS" : "FAIL", ret, live_bytes);
      fails += !ok; }
    return fails ? 1 : 0;
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dp_c")
    ap.add_argument("--expect-fail", action="store_true")
    a = ap.parse_args()
    src = Path(a.dp_c).read_text()
    fns = [function(src, "ath11k_dp_srng_cleanup"), function(src, "ath11k_dp_srng_setup")]
    hal = sorted(set(re.findall(r"\bHAL_[A-Z0-9_]+\b", "".join(fns))) - {"HAL_RING_BASE_ALIGN"})
    if "HAL_RXDMA_DST" not in hal:
        hal.append("HAL_RXDMA_DST")
    consts = ("#define fallthrough __attribute__((__fallthrough__))\n"
              "enum hal_ring_type { " + ", ".join(f"{n} = {i + 1}" for i, n in enumerate(hal)) + " };\n")
    rings = ", ".join(f'{{"{n}", {e}, {c}, {k}}}' for n, e, c, k in RINGS)
    code = HEADER + consts + "\n".join(fns) + MAIN.replace("%RINGS%", rings)
    with tempfile.TemporaryDirectory() as d:
        c, exe = Path(d, "r.c"), Path(d, "r")
        c.write_text(code)
        subprocess.run(["cc", "-std=gnu11", "-w", "-Werror=implicit-function-declaration",
                        "-o", str(exe), str(c)], check=True)
        rc = subprocess.run([str(exe)]).returncode
    if a.expect_fail:
        print("PASS checks detect the unpatched ring sizing" if rc else "FAIL unpatched sizing passed")
        return 0 if rc else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
