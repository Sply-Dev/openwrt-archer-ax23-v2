# Host-side ath11k and Q6 checks

These tests operate on prepared source files from an OpenWrt build tree. They do not require a router, firmware image, private calibration data, or network access.

```sh
python3 tests/host/check_ath11k_ring_alloc.py /path/to/openwrt/build_dir/target-*/linux-qualcommax_ipq50xx/mac80211-*/backports-*/drivers/net/wireless/ath/ath11k/dp.c
python3 tests/host/check_ath11k_cleanup.py /path/to/openwrt/build_dir/target-*/linux-qualcommax_ipq50xx/mac80211-*/backports-*/drivers/net/wireless/ath/ath11k/dp.c
python3 tests/host/check_mpd_recovery.py /path/to/openwrt/build_dir/target-*/linux-qualcommax_ipq50xx/linux-*/drivers/remoteproc/qcom_q6v5_mpd.c
python3 -m unittest discover -s tests/host -p 'test_*.py'
```

The first three programs compile extracted driver functions into host-side C models:
- `check_ath11k_ring_alloc.py` verifies exact DMA ring sizing and runtime alignment checks (`ath11k/965`, wrapper `0013`).
- `check_ath11k_cleanup.py` verifies descriptor-bank ownership unwinding and partial `ath11k_dp_alloc()` failure cleanup (`ath11k/963` and `ath11k/964`, wrappers `0010` and `0011`).
- `check_mpd_recovery.py` verifies nine Q6 multi-PD root/user-PD recovery and reference-counting scenarios (`S1`–`S9`, including repeated user-PD recovery attempts while the root PD is in `RPROC_CRASHED`, `qualcommax/0821`, wrapper `0012`).

The MPD model is not the Linux workqueue, full remoteproc core, SCM, hardware, or a proof of deadlock freedom. The DMA model approximates `dma-direct` page-order allocation and does not exercise a real DMA API/IOMMU. Physical hardware testing is still required to validate QMI/BDF acceptance, dual-radio initialization, sustained throughput, and Q6 crash recovery on the router.
