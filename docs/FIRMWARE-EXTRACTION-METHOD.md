# Firmware extraction method

This document describes, at the method level, how the vendor firmware image for
this device was unpacked through signature verification, payload decryption,
UBI layout inspection, and kernel/rootfs extraction. This is the pipeline
referenced at a high level in `RESEARCH.md`'s "Provenance" section; this document
goes one level deeper into the mechanism, still without reproducing any
artifact-specific secret or the firmware/rootfs itself.

See `README.md` for the evidence-tagging legend used throughout this repository.

**What this document intentionally omits**, consistent with this repository's
publication policy (see `KNOWN-ISSUES.md` and `README.md`): the recovered AES
key/IV, the firmware header's MD5 field value, the decrypted firmware payload,
the extracted rootfs, any `.ko`/`.bin`/`.squashfs`/`.ubi` artifact, and anything
specific to the physical device this was performed against (its network
configuration, service ports, credentials, or any other per-device state).
The following procedure describes the mechanism in enough detail for
someone with the public firmware download and standard tooling to reproduce it.

## Why this matters for the port

This extraction method enabled the analysis in `docs/RESEARCH.md`.
The switch driver analysis, chip detection, MDIO protocol and reset
sequence documented there came from inspecting `qca-ssdk.ko`.
The extraction chain below exposes that module from the vendor's signed,
encrypted firmware image.

## High-level pipeline

```text
vendor .bin firmware image
        |
        v
header (image size, header hash, metadata) + RSA signature
        |
        v
RSA-PSS / SHA-256 signature verification
        |
        v
AES-CBC payload decryption (key material derived from PSS verification data)
        |
        v
UBI container
        |
        +-------------------+
        |                   |
        v                   v
    kernel volume      rootfs volume
        |                   |
        v                   v
    FIT image            SquashFS
        |                   |
        v                   v
  Linux 4.4.60 kernel   OpenWrt-derived rootfs
```

`[OBSERVED]` Every stage of this pipeline was reproduced end-to-end against the
publicly downloadable `1.1.2 Build 20250814` firmware release during this
project's research phase. The result (kernel + rootfs) is what made the
`qca-ssdk.ko` analysis in `RESEARCH.md` possible.

## Stage 1: Header and signature

`[VERIFIED]` The firmware's layout, confirmed against the public
`1.1.2 Build 20250814` download:

| Offset | Field |
|---|---|
| `0x00` | Total image size (big-endian); matches the file's actual size |
| `0x04` | 16-byte header hash field |
| `0x14` | Firmware metadata (build/channel info) |
| `0x130` | RSA-2048 signature (`0x100` bytes) |
| `0x230` | Start of the encrypted payload |

`[SOURCE]` TP-Link's own published GPL archive for this device
(`GPL_AX23v2.tar.gz`, available from TP-Link's GPL Code Center; see
`KNOWN-ISSUES.md` §7 for the same archive referenced in the switch driver
context) includes the firmware-update and signature-verification logic for this
device, under its `nvrammanager` component (`rsaVerify.c`, `nm_fwup.c`). That
source defines these same offsets as constants and was used as the reference
implementation while reproducing the verification step.

## Stage 2: Signature verification

`[SOURCE]`/`[VERIFIED]` The firmware verifier uses RSA-PSS with SHA-256 and
MGF1, consistent with the GPL `nvrammanager` source. Verification against the
publicly downloadable firmware succeeded using the vendor's own embedded public
key material (no private key was needed or recovered; verification only
requires the public half, which is intentionally present in the firmware itself
so the device can check images before flashing them). The PSS trailer byte and
salt length follow the standard RSA-PSS construction and were confirmed to
match what a standard RSA-PSS/SHA-256 verifier produces against this image.

## Stage 3: Payload decryption

`[SOURCE]`/`[VERIFIED]` The encrypted payload (from `0x230` to the end of the
file) is decrypted with AES in CBC mode, without PKCS#7 padding. Per the GPL
source, the AES key and IV used for this are not stored separately in the
firmware; they are derived directly from the RSA-PSS salt recovered during
verification in the previous stage:

```text
salt[0:16]  -> AES-128 key
salt[16:32] -> AES IV
```

This is a deliberate design choice on the vendor's part: it ties payload
decryption to successful signature verification, rather than using an
independent, separately embedded key. Standard tooling (e.g. `openssl enc
-aes-128-cbc -d -nopad`) applied with this key/IV produces a valid UBI image
from the public firmware download.

The specific key and IV bytes recovered during this project's analysis are not
reproduced in this repository (see the scope note at the top of this
document). Those two 16-byte values are artifact-specific outputs of
decrypting a particular build, and this repository does not redistribute
them. The material needed to derive them independently is documented
here: the salt-to-key/IV mapping, the GPL source reference and the
public firmware image.

## Stage 4: UBI container

`[OBSERVED]` The decrypted payload is a UBI (Unsorted Block Image) container,
a standard flash filesystem format used across most OpenWrt NAND targets, not
anything vendor-specific. Within it, two volumes are present: one holding the
kernel, one holding the root filesystem. This matches the general shape any UBI
tooling (`ubireader`, `mtd-utils`) expects and does not require vendor-specific
handling once the payload is decrypted.

## Stage 5: Kernel (FIT image)

`[OBSERVED]` The kernel volume is a standard U-Boot FIT (Flattened Image Tree)
image in a standard, vendor-independent format. It bundles the LZMA-
compressed Linux kernel alongside multiple candidate device tree blobs (DTBs)
for different board variants sharing the same firmware family; the kernel
identifies itself as Linux 4.4.60. The multiple DTBs are why `HARDWARE.md` and
`DEVICE-TREE.md` treat the OEM device tree as a reference to extract specific
facts from (GPIO map, partition layout, chip identification) rather than
something to adapt wholesale into this port's own DTS; the OEM tree describes
OEM Linux 4.4, not upstream OpenWrt's current kernel.

## Stage 6: Root filesystem (SquashFS)

`[OBSERVED]` The rootfs volume is a standard SquashFS image (XZ-compressed).
Extracting it is what exposed `qca-ssdk.ko` and the rest of the vendor
userspace referenced throughout `RESEARCH.md`. The extracted tree follows a
fairly standard OpenWrt-derived layout (`etc/`, `usr/`, `www/`, region-specific
directories for different markets), consistent with this device's lineage.

## Why the decrypted artifacts themselves aren't in this repository

This is covered in principle in `README.md` and `KNOWN-ISSUES.md` §7, and
restated here specifically for the firmware pipeline:

- The decrypted payload, extracted kernel, and extracted rootfs are **not this
  project's own work product**; they are the vendor's firmware, merely
  unwrapped. Redistributing them isn't necessary for anyone to reproduce this
  analysis; the public firmware download plus the method above is sufficient.
- Some components inside the rootfs (like `qca-ssdk.ko`, see `KNOWN-ISSUES.md`
  §7) have licensing provenance that isn't fully resolved; `Dual BSD/GPL` is
  declared, but the vendor's own published GPL archive doesn't include a
  matching source directory for that specific module. Redistributing the
  binary doesn't help resolve that; redistributing the *findings* from
  analyzing it (as `RESEARCH.md` does) does.
- The recovered AES key/IV and header hash are, mechanically, just verification
  artifacts of this specific firmware build, derivable by anyone following the
  method above against the same public download. The method is fully described above. The literal bytes are omitted
  because this repository documents the reproducible process rather than
  distributing a precomputed result.

## Relationship to the configuration backup format

`[OBSERVED]` This device also has a separate encryption chain for its
configuration backup/restore feature (AES-CBC + zlib + TAR, wrapping a
configuration XML), independent of the firmware signing/encryption chain
described above. That mechanism involves per-device state and was not fully
generalized during this project's research, so it is intentionally **not**
documented here or elsewhere in this repository; doing so safely would require
distinguishing device-specific values from genuinely general vendor behavior
more carefully than the current research notes do, and getting that
distinction wrong in a published document is exactly the kind of mistake this
repository is trying to avoid making.
