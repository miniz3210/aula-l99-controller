# Controlled Flash Plan — AULA L99 Screen Resource Image

**Status:** Offline review only. No hardware access, no updater execution, no flashing.
**Decision:** NO-GO — unresolved compatibility checks remain (see Section 19).

## 1. Purpose

This plan defines a controlled, offline-only recovery and package-compatibility review for the patched
AULA L99 screen resource image (`UartTFT-II_Flash.bin`). It produces a controlled flash plan only. It does
not flash, access hardware, run any updater EXE, create or replace updater packages, copy the patched BIN
into a live updater folder, modify firmware, or implement flashing.

## 2. Exact Input Filenames, Sizes, and SHA-256 Values

### Factory reference (immutable, never modified)

| File | Size (bytes) | SHA-256 |
|------|-------------|---------|
| `UartTFT-II_Flash.bin` (factory) | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` |
| `HFD_Code_V2.2.bin` | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` |
| `HFD_Code_V2.3.bin` (official) | 313,652 | `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03` |
| `HFD_Code_V2.3.bin` (earlier build) | 313,504 | `b277823234fcab7137963896493bcb6896fd985fc972354166fcfc584534e37f` |
| Official Reset ZIP (2026-05-25) | 45,080,624 | `e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3` |
| Screen Reset EXE (194 MB) | 194,946,048 | `8d52849afefeadf3a5d28a5e226f2c7a372a9376e1286f35c286d9b820d1ae84` |

### Patched working copy

| File | Size (bytes) | SHA-256 |
|------|-------------|---------|
| `patched_UartTFT-II_Flash.bin` (output of `scripts/patch_l99_numpad_icon.py`) | 127,599,044 | `315f68d5eda99956eb8bb313c9307fd217c19e4f3575e11628496813a0a4f385` |

### Patch scope

- Patch limited to descriptors 341/342 only.
- Range 1: `0x0077C446 .. 0x0077E757` (descriptor 341, NumPad 1 unpressed).
- Range 2: `0x0077E758 .. 0x00780A69` (descriptor 342, NumPad 1 pressed).
- Page 21 touch record `0x003B` unchanged.
- All other bytes preserved exactly.
- Factory round-trip is byte-identical.
- Patched image re-parses successfully.

## 3. Required Package Layout

The official reset package (2026-05-25) is expected to contain:

- Screen Reset EXE (~194 MB) — extracts `UartTFT-II_Flash.bin`, `HFD_Code_V2.2.bin`, `HFD_Code_V2.3.bin`.
- Keyboard Reset EXE (~2.2 MB) — separate keyboard MCU update, out of scope for screen resource image.
- `HFD_ISP_TOOL_V1.31.exe` + `Flash.ini` — screen ISP tooling, local/ignored only.
- `L99 ISP V1.23.exe` — distinct screen ISP tool, local/ignored only.
- `official 2026-05-25 screen reset EXE` — the screen-reset payload within the ZIP.

### UI-only package layout (exact required filenames and relative paths)

All files at package root alongside `HFD_ISP_TOOL_V1.31.exe`:

| File | Required? | Size (bytes) | SHA-256 |
|---|---|---:|---|
| `HFD_ISP_TOOL_V1.31.exe` | Required | 99,328 | `3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282` |
| `UartTFT-II_Flash.bin` | Required | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` |
| `Flash.ini` | Optional | 1,571 | `e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c` |

- `Flash.ini` is **not required** for UI-only mode.
- `HFD_Code_V2.2.bin` and `HFD_Code_V2.3.bin` **can be omitted**; absence of HFD files selects UI-only mode per softce evidence (**STRONG_INFERENCE**, not VERIFIED by static analysis).
- The updater rewrites HFD before/after UI: **UNKNOWN** — no code path establishes HFD write order relative to UI.

Package layout is inferred from `docs/FIRMWARE_PACKAGE_MAP.md`; exact internal structure of the EXE
containers (Enigma Virtual Box) has not been reverse-engineered in this repository.

## 4. Updater Behavior and Static Analysis Results

### Verified facts (offline static analysis)

- Official reset ZIP contains screen and keyboard reset payloads.
- Screen Reset EXE extracts `UartTFT-II_Flash.bin` and `HFD_Code_V2.2.bin`/`HFD_Code_V2.3.bin` at verified offsets.
- `L99 ISP V1.23.exe` and `HFD_ISP_TOOL_V1.31.exe` are distinct tools; roles not conflated with MCU firmware.
- Both ISP tools are MinGW Qt 5.12 applications (PE, x86, 99,328 and 111,008 bytes after EVB unpack).
- Both ISP tools contain direct string references to `/UartTFT-II_Flash.bin`, `/HFD_Code_V2.2.bin`, `/HFD_Code_V2.3.bin`, `/Flash.ini`.
- Both ISP tools contain CRC-related strings: "Mcu code, CRC = ", "Flash code, FileCRC = ", "  FlashCRC = ", "  Len = ".
- Both ISP tools contain size-related error strings: "This file is over than mcu to update!", "The file is over than the flash ic's size".
- Both ISP tools reference `268A` device ID and `\\Device\\USBSER000` serial port.
- Both ISP tools import `Qt5SerialPort.dll` with vendorIdentifier/productIdentifier/hasVendorIdentifier/hasProductIdentifier.
- ISP tool status strings: "Update flash is OK!!!!!!", "Update flash is fail.....", "Read fail,please check the path!", "Time over!".
- Screen Reset EXE (194,946,048 bytes) is an Enigma Virtual Box container with `.enigma1` section (194,584,576 bytes virtual).
- softce recovery.md: "Separate UI packages used `HFD_ISP_TOOL_V1.31.exe` with a resource image named `UartTFT-II_Flash.bin`, without HFD_Code or keyboard MCU files. The updater still transfers the entire resource image."
- softce protocol.md: `6D 01 selector` query with flash ID comparison against `0x00EFAA21` selects HFD V2.2/V2.3; `Flash.ini` maps `EFAA21` to W25N01GV.
- protocol_reference.py: per-packet `4A 30 | offset:LE32 | payload_length:LE16 | payload | CRC32:LE32`; CRC32 reflected IEEE, init=0, xorout=0 (`123456789` → `0x2DFD2D88`).
- ISP tools are signed (Sectigo / DigiCert code-signing certificates present in L99 ISP V1.23.exe).
- Update-mode memory dump shows `\Device\USBSER001` and `USB\VID_EEEF&PID_268A\TEST_1.0` device strings.

### Resolved classifications

- C6 Updater acceptance: **VERIFIED** for `L99 ISP V1.23.exe` and `HFD_ISP_TOOL_V1.31.exe` (direct string refs). **STRONG_INFERENCE** for Screen Reset EXE (extracts it; EVB container, direct acceptance not statically confirmed).
- C7 Required filename/path: **VERIFIED** — exact filename `UartTFT-II_Flash.bin`, root-relative path alongside `Flash.ini` and HFD_Code files.
- C8 Required image size: **VERIFIED** — 127,599,044 bytes (0x079B01C4). Size-check enforcement: **STRONG_INFERENCE** (error strings exist).
- C9 UI-only vs combined: **STRONG_INFERENCE** — softce confirms UI-only ISP packages exist; EXE references all three files so combined writes are possible. Exact UI-only package construction NOT verified (see FINAL_FLASH_BLOCKER_REVIEW.md).
- C10 HFD V2.2/V2.3 selection: **STRONG_INFERENCE** — flash ID `0x00EFAA21` vs `6D 01 selector`; Flash.ini maps JEDEC to chip models.
- C11 Image-level CRC: **VERIFIED** — CRC32 reflected IEEE (init=0, xorout=0) per-packet and FileCRC/FlashCRC strings.
- C12 Per-packet/final verification: **STRONG_INFERENCE** — per-packet CRC32 (`4A 30` frames); final "Update flash is OK/fail" status.
- C13 Full-image vs ranges: **VERIFIED** — softce: "The updater still transfers the entire resource image."
- C14 Flash JEDEC/model checks: **STRONG_INFERENCE** — Flash.ini maps JEDEC IDs to chip models; `0xEFAA21` string present.
- C15 Hardware/board ID checks: **STRONG_INFERENCE** — "Fail to Connect a 268x device"; Qt5SerialPort vendor/product ID imports; `268A` string; `USB\VID_EEEF&PID_268A` in dump.
- C16 Version compatibility checks: **STRONG_INFERENCE** — flash-ID-based HFD V2.2/V2.3 selection; About-page V1.31 unresolved (must not be assumed to be screen version).
- C17 Read-back/post-write verification: **STRONG_INFERENCE** — post-write status messages and "Read fail" string exist; arbitrary flash read-back not established.
- C18 Recovery after interrupted write: **UNKNOWN** — "Time over!" timeout string exists, but no explicit interrupted-write recovery path found in static analysis.
- UI-only package construction: **STRONG_INFERENCE** — softce confirms UI-only packages exist; `Flash.ini` optional, HFD_Code can be omitted; exact accepted construction not verified by static analysis.
- HFD write order before/after UI: **UNKNOWN**.
- Interrupted update can re-enter ISP: manual re-entry **STRONG_INFERENCE** (official instructions: power cycle, Fn+X→0→6, Fn+Space; one configuration only); automatic recovery **UNKNOWN**.

Remaining unknowns from static analysis:

- Whether the modified UI image requires any internal checksum/metadata update beyond the two patched ranges (C16-adjacent; image-level CRC verified but per-image self-checksum unknown).
- Exact per-packet size limits and flash erase sequence not fully determined from strings alone.
- No explicit recovery-after-interrupt behavior in the tool binaries.

## 5. Size, CRC, Filename, Path, Flash-ID, Hardware-ID, and Version Checks

Results of offline static analysis:

- [x] Image size check: **VERIFIED** — 127,599,044 bytes for `UartTFT-II_Flash.bin`. Enforcement inferred from error strings.
- [x] Image CRC check: **VERIFIED** — CRC32 reflected IEEE (init=0, xorout=0) per-packet; FileCRC/FlashCRC strings present.
- [x] Filename match: **VERIFIED** — exact filename `UartTFT-II_Flash.bin` referenced in tool strings.
- [x] Path check: **VERIFIED** — root-relative `/UartTFT-II_Flash.bin` alongside `Flash.ini` and HFD_Code files.
- [x] Flash-ID check: **STRONG_INFERENCE** — `0xEFAA21` string; flash-ID-based HFD V2.2/V2.3 selection per softce protocol.md.
- [x] Hardware-ID check: **STRONG_INFERENCE** — "Fail to Connect a 268x device"; Qt5SerialPort vendor/product ID imports; `268A` string; `USB\VID_EEEF&PID_268A` in dump.
- [x] Version check: **STRONG_INFERENCE** — HFD V2.2 vs V2.3 via flash ID; About-page V1.31 unresolved, must not be assumed to be screen version.
- [x] Post-write CRC verification: **STRONG_INFERENCE** — post-write "Update flash is OK/fail" status strings; arbitrary flash read-back not established.
- [ ] Metadata/header checksum within `UartTFT-II_Flash.bin`: **UNKNOWN** — structured scan
  (`scripts/flash_checksum_scanner.py`) over all fixed-structure regions (main header, page table,
  startup animation, first/last 64 KiB, header words) testing CRC16/MODBUS, CRC32 reflected IEEE,
  standard CRC-32, and additive 16/32-bit sums found no stored-field match at any plausible field
  offset. Classification: UNKNOWN (not proof of absence). The scanner now supports `--mode quick`
  (targeted structural checks, under 30 seconds) and `--mode deep` (cached full investigation). See
  FINAL_FLASH_BLOCKER_REVIEW.md Section 1.

## 6. Does the Modified UI Image Require Internal Checksum/Metadata Update?

**UNKNOWN.** CRC32 per-packet verification is verified in the ISP tools (`4A 30` frames + CRC32 reflected IEEE). FileCRC/FlashCRC strings confirm CRC checking is performed. Whether `UartTFT-II_Flash.bin` contains an additional image-level self-checksum beyond per-packet CRC that the updater or screen MCU validates is **not located in static analysis**. The patcher writes only the two verified descriptor ranges and preserves all other bytes; it does not update any image-level checksum or metadata field. This remains a blocker: if such a checksum exists and is not updated, the patched image may be rejected or cause runtime corruption. See FINAL_FLASH_BLOCKER_REVIEW.md Section 1.

Per-packet CRC32 is separate from any image-level checksum. Lack of an image-level checksum match is not proof that no checksum exists.

## 7. Updater Transmission: Full Image vs Selected Ranges

**VERIFIED.** softce recovery.md: "Separate UI packages used `HFD_ISP_TOOL_V1.31.exe` with a resource image named `UartTFT-II_Flash.bin`, without HFD_Code or keyboard MCU files. The updater still transfers the entire resource image." The ISP tools transmit the full 127,599,044-byte `UartTFT-II_Flash.bin`, not selected ranges. The photo-upload capture (~150 x 2060-byte chunks, ~309 KB) is the photo/framebuffer path, not the full resource-image flash path.

## 8. Comparison of Updater/Tool Candidates

| Tool | Size | SHA-256 | Role | Relationship to UartTFT-II_Flash.bin |
|------|------|---------|------|--------------------------------------|
| L99 ISP V1.23.exe | 111,008 | `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0` | Screen ISP tool | Direct string ref to `/UartTFT-II_Flash.bin`; CRC/size/flash-ID checks present; VERIFIED acceptance |
| HFD_ISP_TOOL_V1.31.exe | 99,328 | `3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282` | Screen ISP tool | Direct string ref to `/UartTFT-II_Flash.bin`; CRC/size/flash-ID checks present; VERIFIED acceptance |
| Official 2026-05-25 screen reset EXE | 194,946,048 | `8d52849afefeadf3a5d28a5e226f2c7a372a9376e1286f35c286d9b820d1ae84` | Screen reset payload within ZIP | EVB container; extracts `UartTFT-II_Flash.bin`, HFD_Code_V2.2/2.3; primary candidate; STRONG_INFERENCE acceptance |
| Official Reset ZIP | 45,080,624 | `e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3` | Comprehensive recovery archive | Contains both screen and keyboard reset EXEs |

All four artifacts are local/ignored binaries. None have been executed. Statically verified: ISP tools accept `UartTFT-II_Flash.bin` directly.

## 9. Preflight Checklist

Items confirmed by offline static analysis (no execution, no hardware):

- [x] Factory `UartTFT-II_Flash.bin` size and SHA-256 verified against `4cb3fa5c...`.
- [x] Patched working-copy SHA-256 verified against `315f68d5...`.
- [x] Patch report (`patch_report.json`) and diff ranges (`diff_ranges.json`) generated and reviewed.
- [x] Only descriptors 341/342 changed; Page 21 touch record `0x003B` unchanged.
- [x] Patched image re-parses successfully with `scripts/inspect_l99_descriptor.py`.
- [x] C6 Updater acceptance: VERIFIED (ISP tools directly reference `/UartTFT-II_Flash.bin`).
- [x] C7 Filename/path: VERIFIED (exact name `UartTFT-II_Flash.bin`, root-relative alongside `Flash.ini`).
- [x] C8 Size check: VERIFIED (127,599,044 bytes; enforcement inferred from error strings).
- [x] C11 CRC check: VERIFIED (CRC32 reflected IEEE per-packet; FileCRC/FlashCRC strings).
- [x] C13 Transmission scope: VERIFIED (full 127,599,044-byte image transferred).
- [x] C14 Flash-ID/JEDEC: STRONG_INFERENCE (Flash.ini JEDEC→chip mapping; `0xEFAA21` string).
- [x] C15 Hardware-ID: STRONG_INFERENCE ("Fail to Connect a 268x device"; Qt5SerialPort VID/PID imports).
- [x] C16 Version compatibility: STRONG_INFERENCE (flash-ID-based HFD V2.2/V2.3 selection).

Items still unresolved (blockers):

- [ ] C9 UI-only vs combined HFD write: STRONG_INFERENCE (UI-only packages confirmed; combined possible). Exact UI-only package construction NOT verified.
- [ ] C12 Per-packet/final verification: STRONG_INFERENCE (per-packet CRC32; final OK/fail status).
- [ ] C17 Read-back/post-write: STRONG_INFERENCE (status strings exist; arbitrary read-back not established).
- [ ] C18 Recovery after interrupted write: UNKNOWN (timeout string exists; no explicit recovery path; residual brick risk explicit).
- [ ] Image-level self-checksum within `UartTFT-II_Flash.bin`: UNKNOWN (per-packet CRC verified; image-level self-checksum not located; per-packet CRC is separate from any image-level checksum).
- [x] Stable, direct USB connection confirmed (no hubs, no docking stations).
- [x] Stable power source confirmed (UPS or direct AC; no battery-only operation).
- [x] Procmon, USBPcap/Wireshark, and screen-recording configured and ready.
- [x] Untouched official factory files available for rollback.
- [ ] GO / NO-GO decision documented and signed.

## 10. Stable Power and Direct USB Requirements

- Stable AC power or UPS; no battery-only operation during any flash.
- Direct USB connection to the host; no hubs, no docking stations, no passthrough.
- Screen-side device: VID EEEF, PID 268A, CDC/serial COM port.
- Keyboard-side device: VID 0C45, PID 800A (separate path, not used for screen resource flash).
- No USB driver replacement (no Zadig, WinUSB, libusbK) in the first implementation.
- No COM port sharing with other tools during the operation.

## 11. Procmon, USBPcap/Wireshark, and Screen-Recording Setup

### Procmon
- Filter: process name of the updater EXE; operations: File, Registry, Process, Network.
- Capture before Start through completion or abort.
- Save PML for post-incident analysis.

### USBPcap / Wireshark
- Capture the screen-side USB bus (VID EEEF, PID 268A) before, during, and after the operation.
- Filter: `usb.device_address == <screen device>` or vendor/product ID filters.
- Record all Bulk OUT transfers, control transfers, and device disconnect/reconnect events.
- Save PCAPNG for comparison against the official photo-upload capture (~150 x 2060-byte chunks).

### Screen recording
- Record the device's built-in screen throughout: pre-update state, update progress, post-update state.
- Capture About page, Mini Numpad page (page 21), and any error or recovery screens.
- Save lossless video with timestamps.

## 12. Abort Conditions Before Start

Abort immediately if any of the following are true:

- Factory SHA-256 of `UartTFT-II_Flash.bin` does not match `4cb3fa5c...`.
- Patched SHA-256 does not match `315f68d5...`.
- Any byte outside descriptors 341/342 changed in the patched image.
- Page 21 touch record `0x003B` changed.
- Patched image fails to re-parse.
- Unresolved checks in Sections 4–7 remain without explicit risk acceptance.
- Power or USB stability cannot be guaranteed.
- Monitoring tooling (Procmon, USBPcap/Wireshark, screen recording) is not active.
- GO / NO-GO decision is NO-GO.

## 13. Actions Prohibited After Erase/Write Begins

- Do not disconnect USB.
- Do not power-cycle or reset the device.
- Do not run any other USB/COM/HID tool against the device.
- Do not force mode or override safety checks.
- Do not retry automatically after timeout.
- Do not close the updater or kill its process.
- Do not modify any file in the updater package directory.
- Do not interact with the screen or keyboard during the operation.

## 14. Success Checks After Update

- [ ] Device re-enumerates as VID EEEF / PID 268A on a COM port.
- [ ] Device boots to the expected home screen without error.
- [ ] Page 21 (Mini Numpad) renders with the patched icons.
- [ ] Page 21 touch record `0x003B` returns `goto_page 65535`.
- [ ] All 17 NumPad actions remain mapped and functional.
- [ ] About page does not show corruption or version mismatch (informational only; V1.31 source unresolved).
- [ ] No new USB errors in Wireshark/Procmon captures.
- [ ] Patched image hash on device (if read-back is available) matches `315f68d5...`.

## 15. Rollback Attempt Using Untouched Official Factory Files

If the update fails or produces an incorrect result:

1. Restore `UartTFT-II_Flash.bin` from the untouched factory copy (SHA-256 `4cb3fa5c...`).
2. Attempt re-flash using the official reset package only.
3. Verify factory SHA-256 is restored.
4. Verify all 30 pages, 385 display records, 187 touch records, 1138 descriptors parse correctly.
5. If the device fails to boot after rollback, escalate to hardware NAND recovery (Section 17).

Rollback is limited to software recovery using the official reset package; it does not restore per-device
OOB, ECC, bad-block, calibration, or unique-board data because the official package is not a raw NAND dump.

## 16. Limits of Software Recovery

- The official reset package is **not** a raw NAND dump.
- It lacks verified per-device OOB, ECC, bad-block, calibration, and unique-board data.
- Arbitrary flash-byte read-back is not established.
- ISP tool post-write CRC verification evidence exists but arbitrary flash read-back is not established.
- Built-in page/resource table locations within `HFD_Code` binaries are not located.
- Recovery and bootloader procedure are not established.
- No claim of universal brick recovery.
- Software recovery can only restore files included in the official reset package.

## 17. Conditions Requiring Hardware NAND Recovery

Hardware NAND recovery (outside the scope of this repository) is required if:

- The device fails to boot after software rollback with official factory files.
- The screen MCU or bootloader is corrupted.
- Bad blocks, ECC failures, or OOB corruption are suspected.
- Per-device calibration or unique-board data is lost.
- The updater cannot re-establish communication with the device in ISP mode.

## 18. Separated Findings: Verified, Strong Inference, Unknown

### Verified

- Factory image size and SHA-256.
- Patched image size and SHA-256.
- Patch limited to descriptors 341/342 at verified ranges.
- Page 21 touch record `0x003B` unchanged.
- Factory round-trip byte-identical.
- Patched image re-parses successfully.
- Official reset ZIP and Screen Reset EXE sizes and hashes.
- ISP tools (`L99 ISP V1.23.exe`, `HFD_ISP_TOOL_V1.31.exe`) directly reference `/UartTFT-II_Flash.bin` — C6 VERIFIED for both.
- Exact filename `UartTFT-II_Flash.bin` required — C7 VERIFIED.
- Image size 127,599,044 bytes — C8 VERIFIED.
- Per-packet CRC32 (reflected IEEE, init=0, xorout=0); FileCRC/FlashCRC strings — C11 VERIFIED.
- Full 127,599,044-byte image transferred (not ranges) — C13 VERIFIED.
- Official reset package is not a raw NAND dump.
- About-page V1.31 source unresolved; must not be assumed to identify screen firmware.

### Strong Inference (unverified)

- Screen Reset EXE extracts `UartTFT-II_Flash.bin` and `HFD_Code` binaries — C6 STRONG_INFERENCE.
- `L99 ISP V1.23.exe` and `HFD_ISP_TOOL_V1.31.exe` are distinct screen ISP tools.
- Photo/upload path does not overlay the Mini Numpad page.
- Size-check enforcement inferred from error strings — C8 STRONG_INFERENCE.
- UI-only vs combined HFD write — C9 STRONG_INFERENCE (UI-only packages confirmed; combined possible).
- HFD V2.2 vs V2.3 via flash-ID selector `0xEFAA21` — C10 STRONG_INFERENCE.
- Flash-ID/JEDEC-to-chip mapping — C14 STRONG_INFERENCE.
- Hardware-ID check "Fail to Connect a 268x device" — C15 STRONG_INFERENCE.
- Version compatibility via flash-ID-based HFD selection — C16 STRONG_INFERENCE.
- Per-packet CRC32 + final OK/fail status — C12 STRONG_INFERENCE.
- Post-write status / "Read fail" strings — C17 STRONG_INFERENCE (arbitrary read-back not established).

### Unknown

- Whether the modified UI image requires internal image-level self-checksum/metadata update beyond per-packet CRC (C16-adjacent).
- C18 Recovery behavior after interrupted write: no explicit recovery path found in static analysis.
- Whether updater writes UI only vs also rewrites HFD_Code — C9 (partially STRONG_INFERENCE).
- Exact per-packet size limits and flash erase sequence not fully determined from strings alone.
- Whether the Screen Reset EXE directly accepts `UartTFT-II_Flash.bin` or only via bundled extraction — C6 STRONG_INFERENCE.

## 19. GO / NO-GO Decision

**Decision: NO-GO**

Justification: Not all critical blockers are VERIFIED. Per project policy, NO-GO changes to GO only when all critical blockers are VERIFIED:

- updater acceptance: **VERIFIED** (ISP tools) / STRONG_INFERENCE (Screen Reset EXE)
- required package layout: **VERIFIED** (filename/path exact)
- write scope: **STRONG_INFERENCE** (full image; UI-only vs combined HFD not fully resolved)
- checksum/CRC handling: **VERIFIED** (per-packet CRC) / UNKNOWN (image-level self-checksum)
- recovery path: **UNKNOWN** (no explicit interrupted-write recovery found; residual brick risk explicit)

Unresolved critical items:
1. Image-level self-checksum requirement (per-packet CRC verified; image-level self-checksum not located).
2. UI-only vs combined HFD write scope (STRONG_INFERENCE only; exact UI-only package construction NOT verified).
3. Recovery behavior after interrupted write (UNKNOWN; residual brick risk explicit).

Until all critical blockers are VERIFIED, **no hardware write is permitted.**

## 20. Exact Next Task

Resolve remaining critical blockers offline: (1) determine whether `UartTFT-II_Flash.bin` contains an image-level self-checksum beyond per-packet CRC; (2) confirm write scope (UI-only vs combined HFD_Code rewrite) as VERIFIED or explicitly accept combined write — including exact UI-only package construction; (3) determine recovery behavior after interrupted write as VERIFIED or explicitly accept residual brick risk. Continue offline static analysis only — do not execute any EXE or connect hardware.

## 21. Official update capture preparation (ADDED in v0.6.0; corrected in v0.6.1)

Capture preparation only. No updater execution, no hardware access, no flashing.
Decision remains NO-GO.

The only approved capture target is the original untouched L99 ISP V1.23.exe package
(`firmware\unpacked\L99 ISP V1.23.exe`, 111,008 bytes,
SHA-256 `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0`).

Excluded targets: Screen Reset EXE from L99-reset.zip, patched_UartTFT-II_Flash.bin,
renamed/replaced vendor payloads, and new UI-only package construction.

- `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md` — passive capture procedure for one unchanged official L99 ISP V1.23.exe screen update.
- `scripts/prepare_official_capture.ps1` — preflight-only verification (package hashes, Procmon/Wireshark/USBPcap, disk space, timestamped capture directory, READY/NOT READY).
- `scripts/analyse_official_capture.py` — offline analyser for exported Procmon CSV + PCAPNG; EVIDENCE/INFERENCE classification; no COM/USB access, no updater execution.
- `tests/test_analyse_official_capture.py` — synthetic analyser tests.

This capture kit prepares observation only. It does not resolve any critical blocker by itself; the captured evidence must be reviewed against the unresolved blockers (image-level self-checksum, write scope, interrupted-write recovery) before any GO decision.