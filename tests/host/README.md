# Host-side ath11k and Q6 checks

These tests operate on prepared source files from an OpenWrt build tree. They do not require a router, firmware image, private calibration data, or network access.

```sh
python3 tests/host/check_ath11k_ring_alloc.py /path/to/openwrt/build_dir/target-*/linux-qualcommax_ipq50xx/mac80211-*/backports-*/drivers/net/wireless/ath/ath11k/dp.c
python3 tests/host/check_mpd_recovery.py /path/to/openwrt/build_dir/target-*/linux-qualcommax_ipq50xx/linux-*/drivers/remoteproc/qcom_q6v5_mpd.c
python3 -m unittest discover -s tests/host -p 'test_*.py'
```

The first two programs compile extracted driver functions into host-side models. They check allocation alignment/size and selected MPD reference/recovery scenarios, including whether the modeled baseline fails. The MPD model is not the Linux workqueue, remoteproc core, SCM, hardware, or a proof of deadlock freedom. The DMA model approximates dma-direct page-order allocation and does not exercise a real DMA API/IOMMU.

A target OpenWrt build is required to verify patch integration and compilation. Physical testing is required for QMI/BDF selection, both radios, sustained traffic, crash recovery, RF/regulatory behavior, and memory pressure. The board-data `-12` failure is not claimed fixed by this series.