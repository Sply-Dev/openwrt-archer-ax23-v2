#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile the prepared driver's allocation functions against host ownership checks."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def function(source, name):
    match = re.search(r"^(?:static\s+)?(?:int|void)\s+" + name + r"\([^;{]+\)\s*\{", source, re.M)
    if not match:
        raise ValueError(f"missing driver definition: {name}")
    return source[match.start():source.index("\n}", match.end()) + 2]


STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef unsigned int u32;
enum { DP_LINK_DESC_BANKS_MAX=8, DP_LINK_DESC_ALLOC_SIZE_THRESH=2097152,
       HAL_LINK_DESC_ALIGN=128, GFP_KERNEL=0, HAL_WBM_IDLE_LINK=1,
       HAL_DSCP_TID_MAP_TBL_NUM_ENTRIES_MAX=8,
       DP_TX_COMP_RING_SIZE_LOWMEM=2048, DP_TX_COMP_RING_SIZE=32768 };
struct dp_link_desc_bank {
    void *vaddr, *vaddr_unaligned;
    uintptr_t paddr, paddr_unaligned;
    int size;
};
struct dp_srng { int ring_id; };
struct hal_srng { int unused; };
struct hal_wbm_release_ring { char bytes[32]; };
struct ath11k_base;
struct ath11k_dp {
    struct ath11k_base *ab;
    struct dp_link_desc_bank link_desc_banks[DP_LINK_DESC_BANKS_MAX];
    struct dp_srng wbm_idle_ring;
    u32 tx_comp_ring_size, reo_cmd_cache_flush_count;
    struct { int tcl_data_ring_id, tx_status_head, tx_status_tail; void *tx_status; } tx_ring[3];
};
struct ath11k_base {
    void *dev;
    struct ath11k_dp dp;
    struct { struct hal_srng srng_list[1]; } hal;
    struct { int fw_mem_mode; struct hal_params { int num_tx_rings; } *hal_params; } hw_params;
};
#define PTR_ALIGN(p, a) ((void *)(((uintptr_t)(p)+(a)-1) & ~(uintptr_t)((a)-1)))
#define INIT_LIST_HEAD(p) ((void)0)
#define spin_lock_init(p) ((void)0)
#define idr_init(p) ((void)0)
#define ath11k_warn(...) ((void)0)
#define ath11k_hal_tx_set_dscp_tid_map(...) ((void)0)
static int allocations, outstanding, fail_at, fail_link, idle, common;
static void *allocate(void) {
    if (++allocations == fail_at) return NULL;
    void *p = malloc(256);
    assert(p);
    ++outstanding;
    return p;
}
static void release(void *p) { assert(p && outstanding > 0); free(p); --outstanding; }
#define dma_alloc_coherent(dev, sz, addr, flags) allocate()
#define dma_free_coherent(dev, sz, ptr, addr) release(ptr)
#define kmalloc(sz, flags) allocate()
#define kfree(ptr) release(ptr)
static int ath11k_wbm_idle_ring_setup(struct ath11k_base *ab, u32 *count) {
    assert(!idle); idle=1; *count=1; return 0;
}
static int ath11k_dp_link_desc_setup(struct ath11k_base *ab, struct dp_link_desc_bank *b,
                                    int type, struct hal_srng *ring, u32 count) {
    return fail_link ? -ENOMEM : 0;
}
static int ath11k_dp_srng_common_setup(struct ath11k_base *ab) {
    assert(!common); common=1; return 0;
}
static void ath11k_dp_srng_common_cleanup(struct ath11k_base *ab) {
    assert(common); common=0;
}
static void ath11k_dp_link_desc_cleanup(struct ath11k_base *ab, struct dp_link_desc_bank *b,
                                       int type, struct dp_srng *ring) {
    assert(idle && ring == &ab->dp.wbm_idle_ring); idle=0;
}
"""

CHECKS = r"""
int main(void) {
    struct hal_params params = { .num_tx_rings=3 };
    struct ath11k_base ab = { .hw_params={ .fw_mem_mode=2, .hal_params=&params } };
    struct dp_link_desc_bank monitor[DP_LINK_DESC_BANKS_MAX] = {0};
    void *guard = allocate();
    ab.dp.link_desc_banks[0].vaddr_unaligned = guard;
    for (int failure=1; failure<=3; ++failure) {
        allocations=0; fail_at=failure;
        assert(ath11k_dp_link_desc_bank_alloc(&ab, monitor, 3, 384) == -ENOMEM);
        assert(outstanding == 1 && ab.dp.link_desc_banks[0].vaddr_unaligned == guard);
        for (int i=0; i<3; ++i) assert(!monitor[i].vaddr_unaligned);
    }
    release(guard);
    ab.dp.link_desc_banks[0].vaddr_unaligned=NULL;
    fail_link=1;
    assert(ath11k_dp_alloc(&ab) == -ENOMEM && !idle && !common);
    fail_link=0;
    for (int failure=1; failure<=3; ++failure) {
        allocations=0; fail_at=failure;
        assert(ath11k_dp_alloc(&ab) == -ENOMEM && !idle && !common && !outstanding);
        for (int i=0; i<3; ++i) assert(!ab.dp.tx_ring[i].tx_status);
    }
    puts("PASS actual driver allocation functions preserve pool ownership and unwind partial startup");
    return 0;
}
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dp_c", type=Path)
    args = parser.parse_args()
    source = args.dp_c.read_text()
    names = ("ath11k_dp_link_desc_bank_free", "ath11k_dp_link_desc_bank_alloc", "ath11k_dp_alloc")
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "check"
        unit = Path(tmp) / "check.c"
        unit.write_text("\n".join([STUBS, *(function(source, name) for name in names), CHECKS]))
        subprocess.run(["cc", "-std=c11", "-O0", "-o", exe, unit], check=True)
        subprocess.run([exe], check=True)
