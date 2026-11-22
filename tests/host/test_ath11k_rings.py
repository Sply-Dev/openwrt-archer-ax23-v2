#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Checks for the ath11k low-memory ring patches (960 RX, 961 TX completion).

1. Static: the patch text keeps every quantity derived from the TX completion
   ring size on the one runtime value (ring, status FIFO, tail init, wrap macro,
   msdu_id IDR range) and leaves no fixed 32768 behind.
2. Model: a line-by-line Python model of ath11k_dp_tx() IDR allocation and
   ath11k_dp_tx_completion_handler() (dp_tx.c, backports-7.2) driven with random
   TX/completion bursts at the low-memory size. Every frame must complete exactly
   once, in order, and the "status_fifo is full" path must never be taken.
3. Memory accounting: allocation orders and bytes per radio, default vs FW mode 2,
   for the TX completion ring (DMA) and its kmalloc FIFO.

Static source analysis and a software model only: nothing here exercises the
real firmware or hardware.
"""
import heapq
import os
import random
import re
import unittest

PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCHES = os.path.join(PROJ, "patches")

PAGE = 4096
WBM_RELEASE_DESC = 32          # sizeof(struct hal_wbm_release_ring): 8 + 3*4 + 8 + 4
HAL_RING_BASE_ALIGN = 8
DEFAULT_TX_COMP = 32768


def patch_text(prefix):
    names = {
        "0002-": "0006-ath11k-low-memory-rx-rings.patch",
        "0012-": "0007-ath11k-low-memory-tx-completion-ring.patch",
        "0018-": "0008-ath11k-low-memory-rx-reference-profile.patch",
    }
    with open(os.path.join(PATCHES, names[prefix])) as fh:
        return fh.read()


def added_lines(text):
    return [l[2:] for l in text.splitlines() if l.startswith("++") and not l.startswith("+++")]


def removed_lines(text):
    return [l[2:] for l in text.splitlines() if l.startswith("+-") and not l.startswith("+--")]


def get_order(size):
    pages = -(-size // PAGE)
    order = 0
    while (1 << order) < pages:
        order += 1
    return order


def lowmem_value():
    m = re.search(r"#define DP_TX_COMP_RING_SIZE_LOWMEM\s+(\d+)", patch_text("0012-"))
    return int(m.group(1))


class StaticPatch(unittest.TestCase):
    def setUp(self):
        self.t = patch_text("0012-")
        self.add = "\n".join(added_lines(self.t))
        self.rem = "\n".join(removed_lines(self.t))

    def test_inner_patch_is_ath11k_961(self):
        self.assertIn("package/kernel/mac80211/patches/ath11k/961-", self.t)

    def test_every_size_user_follows_runtime_value(self):
        for needle in ("dp->tx_comp_ring_size);",                       # srng setup
                       "* dp->tx_comp_ring_size;",                      # FIFO kmalloc size
                       "tx_status_tail = dp->tx_comp_ring_size - 1;",   # FIFO tail
                       "% (dp)->tx_comp_ring_size)",                    # wrap macro
                       "dp->tx_comp_ring_size - 2, GFP_ATOMIC);"):      # IDR range
            self.assertIn(needle, self.add, needle)
        for gone in ("DP_TX_IDR_SIZE", "% DP_TX_COMP_RING_SIZE)", "DP_TX_COMP_RING_SIZE);",
                     "tx_status_tail = DP_TX_COMP_RING_SIZE - 1;"):
            self.assertIn(gone, self.rem, gone)

    def test_all_wrap_macro_users_converted(self):
        self.assertEqual(self.add.count("ATH11K_TX_COMPL_NEXT(dp, tx_ring->"), 5)
        self.assertEqual(self.rem.count("ATH11K_TX_COMPL_NEXT(tx_ring->"), 5)

    def test_size_chosen_before_rings_are_created(self):
        i = self.add.find("dp->tx_comp_ring_size = ab->hw_params.fw_mem_mode == 2")
        self.assertGreaterEqual(i, 0)
        body = self.t[self.t.find("ath11k_dp_alloc"):]
        self.assertLess(body.find("dp->tx_comp_ring_size = "),
                        body.find("ath11k_wbm_idle_ring_setup(ab"))

    def test_same_selector_as_rx_patch_and_no_overlap(self):
        rx = patch_text("0002-")
        self.assertIn("ab->hw_params.fw_mem_mode == 2", rx)
        self.assertNotIn("tx_comp_ring_size", rx)
        self.assertNotIn("RXDMA", "\n".join(added_lines(self.t)))

    def test_lowmem_is_power_of_two_and_above_tcl_ring(self):
        n = lowmem_value()
        self.assertEqual(n & (n - 1), 0)
        self.assertGreater(n, 512)          # DP_TCL_DATA_RING_SIZE
        self.assertLess(n, DEFAULT_TX_COMP)


class RxReferenceValues(unittest.TestCase):
    """0018 (ath11k 962): RX ring sizes in FW memory mode 2 follow the published
    low-memory profiles (ath-next proposal, PR #21495, QSDK 512M)."""

    def setUp(self):
        self.t = patch_text("0018-")
        self.add = "\n".join(added_lines(self.t))
        self.rem = "\n".join(removed_lines(self.t))

    def test_rxdma_buffer_ring_is_1024_on_both_radios(self):
        self.assertIn("#define DP_RXDMA_BUF_RING_SIZE_LOWMEM\t\t1024", self.add)
        self.assertIn("DP_RXDMA_BUF_RING_SIZE_LOWMEM_QCN6122", self.rem)
        self.assertNotIn("ATH11K_HW_QCN6122_HW10", self.add)

    def test_error_destination_ring_keeps_default(self):
        self.assertIn("DP_RXDMA_ERR_DST_RING_SIZE_LOWMEM", self.rem)
        self.assertNotIn("DP_RXDMA_ERR_DST_RING_SIZE_LOWMEM", self.add)
        self.assertIn("return DP_RXDMA_ERR_DST_RING_SIZE;", self.add)


class CompletionModel(unittest.TestCase):
    """Python model of dp_tx.c with the patched macro; srng = capacity size-1."""

    def run_model(self, size, seed, steps=20000, idr_end=None):
        rnd = random.Random(seed)
        nxt = lambda x: (x + 1) % size                         # ATH11K_TX_COMPL_NEXT(dp, x)
        if idr_end is None:
            idr_end = size - 2                                 # patched: idr_alloc(.., 0, size - 2)
        idr = set()                                            # txbuf_idr, ids in [0, idr_end)
        free_ids = list(range(idr_end))                        # idr_alloc() returns the lowest free id
        hw = []                                                # WBM2SW ring (FIFO order)
        fifo = [None] * size                                   # tx_ring->tx_status
        head, tail = 0, size - 1
        inflight, done, drops, fifo_full_warn = [], [], 0, 0
        seq = 0
        for _ in range(steps):
            for _ in range(rnd.randint(0, 64)):                # TX burst: ath11k_dp_tx()
                if not free_ids:
                    drops += 1                                 # -ENOSPC (single TX ring on IPQ5018)
                    continue
                free = heapq.heappop(free_ids)
                idr.add(free)
                inflight.append((free, seq))
                seq += 1
            for _ in range(rnd.randint(0, 64)):                # FW releases in order
                if not inflight:
                    break
                self.assertLess(len(hw), size - 1, "WBM2SW ring would overflow")
                hw.append(inflight.pop(0))
            if rnd.random() < 0.5:                             # NAPI: completion handler
                while nxt(head) != tail and hw:
                    fifo[head] = hw.pop(0)
                    head = nxt(head)
                if hw and nxt(head) == tail:
                    fifo_full_warn += 1
                while nxt(tail) != head:
                    tail = nxt(tail)
                    msdu_id, s = fifo[tail]
                    self.assertIn(msdu_id, idr)
                    idr.remove(msdu_id)                        # idr_remove() + skb free
                    heapq.heappush(free_ids, msdu_id)
                    done.append(s)
            self.assertLessEqual(len(idr), size - 1)
        return done, drops, fifo_full_warn, seq

    def test_lowmem_ring_in_order_exactly_once(self):
        n = lowmem_value()
        for seed in range(3):
            done, drops, warn, sent = self.run_model(n, seed)
            self.assertEqual(done, sorted(done))
            self.assertEqual(len(done), len(set(done)))
            self.assertEqual(warn, 0)

    def test_upstream_bound_can_strand_a_completion(self):
        # idr end = size - 1 (upstream DP_TX_IDR_SIZE - 1, also the ath-next proposal):
        # size - 1 frames in flight, but one handler pass moves only size - 2 into the
        # FIFO -> "status_fifo is full" path. Unreachable at 32768 in practice, reachable
        # at 2048 under load; the patch bounds the IDR at size - 2 instead.
        done, drops, warn, sent = self.run_model(16, 7, steps=3000, idr_end=15)
        self.assertGreater(warn, 0)
        self.assertEqual(done, sorted(done))                   # still no loss, only delay

    def test_small_ring_exercises_wrap_and_backpressure(self):
        done, drops, warn, sent = self.run_model(16, 7, steps=3000)
        self.assertGreater(drops, 0)                           # IDR bound reached, frames refused
        self.assertEqual(done, sorted(done))
        self.assertEqual(warn, 0)
        self.assertGreater(len(done), 16 * 10)                 # wrapped many times


class MemoryAccounting(unittest.TestCase):
    def per_radio(self, entries):
        ring = entries * WBM_RELEASE_DESC + HAL_RING_BASE_ALIGN - 1   # ath11k_dp_srng_setup()
        fifo = entries * WBM_RELEASE_DESC                             # kmalloc in ath11k_dp_alloc()
        return get_order(ring), (PAGE << get_order(ring)), get_order(fifo), (PAGE << get_order(fifo))

    def test_default_needs_order9_dma_and_order8_kmalloc(self):
        o_ring, b_ring, o_fifo, b_fifo = self.per_radio(DEFAULT_TX_COMP)
        self.assertEqual((o_ring, b_ring), (9, 2 << 20))
        self.assertEqual((o_fifo, b_fifo), (8, 1 << 20))

    def test_lowmem_saving_both_radios(self):
        d = self.per_radio(DEFAULT_TX_COMP)
        l = self.per_radio(lowmem_value())
        self.assertEqual((l[0], l[2]), (5, 4))
        saved = 2 * ((d[1] + d[3]) - (l[1] + l[3]))    # IPQ5018 + QCN6122, one TX ring each
        self.assertEqual(saved, 2 * (3 << 20) - 2 * (192 << 10))
        print("\n  TX completion: default %d KiB/radio (orders %d+%d), FW mode 2 %d KiB/radio "
              "(orders %d+%d); saved %.2f MiB for two radios"
              % ((d[1] + d[3]) >> 10, d[0], d[2], (l[1] + l[3]) >> 10, l[0], l[2], saved / 2**20))


if __name__ == "__main__":
    unittest.main()
