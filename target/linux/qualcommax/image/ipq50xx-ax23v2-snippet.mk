# Snippet extracted from target/linux/qualcommax/image/ipq50xx.mk
# This file contains only the Device/tplink_archer-ax23-v2 definition.
# In the OpenWrt tree, this block belongs in target/linux/qualcommax/image/ipq50xx.mk
# (after mercusys_mr80x-v2 and before tplink_archer-ax55-v1).

define Device/tplink_archer-ax23-v2
	$(call Device/FitImageLzma)
	$(call Device/UbiFit)
	DEVICE_VENDOR := TP-Link
	DEVICE_MODEL := Archer AX23
	DEVICE_VARIANT := v2
	DEVICE_DTS_CONFIG := config@mp02.1
	SOC := ipq5018
	DEVICE_DTS := ipq5018-archer-ax23-v2
	BLOCKSIZE := 128k
	PAGESIZE := 2048
	IMAGE_SIZE := 54784k
	NAND_SIZE := 128m
	DEVICE_PACKAGES := ath11k-firmware-ipq5018-qcn6122 \
		kmod-dsa-rtl8365mb
ifneq ($(CONFIG_TARGET_ROOTFS_INITRAMFS),)
ifeq ($(IB),)
	ARTIFACTS := initramfs-factory.ubi
	ARTIFACT/initramfs-factory.ubi := append-image-stage initramfs-uImage.itb | ubinize-kernel
endif
endif
endef
TARGET_DEVICES += tplink_archer-ax23-v2
