# Changelog

## Unreleased

### Added
- Optimised `scripts/flash_checksum_scanner.py` with `--mode quick` (targeted structural checks,
  no exploratory whole-image candidate scanning, target under 30 seconds on the 127,599,044-byte
  factory image) and `--mode deep` (full structural investigation, cached by factory hash, patched
  hash, scanner version, scanner source hash, algorithm list, and region-map hash). Cache hit returns
  immediately. Uses native C-backed CRC32 (zlib), lookup-table CRC16/MODBUS and CRC32/standard,
  ProcessPoolExecutor parallelisation across `min(8, physical CPU cores)` workers (never
  ThreadPoolExecutor for CPU-bound work), single full-image read, per-region single algorithm
  computation, configurable `--max-runtime` guard, and phase/progress/timing output.
- Added synthetic tests for quick/deep modes, cache creation, cache-hit on identical key, cache
  invalidation on changed scanner version/source hash/algorithm list/region map, deterministic cached
  output, false-positive CRC16 collision handling, timeout guard, source-image immutability, and
  multiprocessing/single-worker equivalence.
- Deleted `scripts/analyze_updater_pe.py` (was a one-off PE analysis tool, not a reusable checksum
  scanner; no longer needed now that PE analysis results are documented).
- Added `docs/UI_ONLY_PACKAGE_CONSTRUCTION.md` — offline static-analysis record of UI-only vs combined package construction. UI-only packages confirmed to exist per softce (STRONG_INFERENCE); exact accepted construction NOT verified. HFD_Code_V2.3 same-name hash discrepancy documented (`evbunpack_output` = earlier build `b2778232...`, 313,504 bytes; `softce/extracted` = official `a76806ad...`, 313,652 bytes).
- Added `docs/PAGE21_FIRST_PATCH_PLAN.md` — Page 21 return code 0x003B, descriptor 341/342 patch plan. Equal-size (8,978-byte) in-place replacement is structurally sufficient: no descriptor-table, page-table, touch-record, global-metadata, or per-resource-checksum changes required. Image-level checksum blocker remains open.

### Changed
- Updated `docs/FIRMWARE_PACKAGE_MAP.md`: added UI-only package construction summary and unresolved-question entries.
- Updated `docs/PROJECT_HANDOVER.md`: added new doc references and blocker status.
- Added synthetic tests `tests/test_inspect_l99_descriptor.py` (32 tests, no vendor firmware required or embedded).
- Verified Page 21 NumPad 1 descriptor mapping via factory validation.
- Recorded descriptor 341/342 findings (offsets, format, dimensions, encoded length, allocation, hashes, references, verified boundaries).
- Recorded patch feasibility as PROVEN_FOR_OFFLINE_WORKING_COPY (offline working copy only; metadata/checksum implications Unknown).
- Added offline-only ARGB4444 encoder and working-copy patcher `scripts/patch_l99_numpad_icon.py` for NumPad 1 descriptors 341/342:
  - Requires exact factory size (127599044) and SHA-256.
  - Writes a separate patched working copy; never modifies the factory image.
  - Byte-for-byte round-trip check on factory descriptors 341/342 before patching.
  - Writes only the two verified ranges (0x0077C446..0x0077E757 and 0x0077E758..0x00780A69).
  - Preserves all other bytes; never touches touch records or descriptor-table entries.
  - Generates patched image, patch_report.json, diff_ranges.json, normal/pressed encoded binaries and round-trip PNGs.
- Added synthetic tests `tests/test_patch_l99_numpad_icon.py` covering ARGB4444 golden vectors, factory round-trip, wrong dimensions, malformed PNG, wrong encoded length, input/output collision, exact two-range patch, all other bytes unchanged, deterministic output, source image unchanged, and factory hash rejection (no vendor firmware required or embedded).
- Added reusable offline static PE analysis script `scripts/analyze_updater_pe.py` (PE metadata, imports, resources, strings; read-only, no EXE execution).
- Added PE analysis reports under `local_analysis/pe_reports/` for `L99 ISP V1.23.exe` and `HFD_ISP_TOOL_V1.31.exe`.
- Completed offline static analysis of updater candidates to resolve blockers C6-C18 (see `docs/CONTROLLED_FLASH_PLAN.md` and `docs/RECOVERY_COMPATIBILITY_MATRIX.md`).

### Changed
- Updated docs/PROJECT_HANDOVER.md: added descriptor 341/342 mapping section, offline patcher section, and marked Workstream A complete with next milestone pointing to recovery/package compatibility review; added controlled flash plan static analysis results.
- Updated README.md: added offline NumPad icon patcher tooling section.
- Updated .gitignore: added local_analysis/.
- Updated docs/CONTROLLED_FLASH_PLAN.md: Sections 4-9 updated with static analysis results; C6-C18 classifications assigned; GO/NO-GO decision retained as NO-GO.
- Updated docs/RECOVERY_COMPATIBILITY_MATRIX.md: Component inventory, relationship matrix, check status C1-C21, UI-only vs full-reset conclusion, checksum/CRC conclusion, GO/NO-GO decision updated.

### Verified
- Factory UartTFT-II_Flash.bin: size 127599044, SHA-256 4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4 — unchanged before/after validation.
- Page 21 return code 0x003B, rectangle [13,337,79,403], unpressed descriptor 341, pressed descriptor 342, goto_page 65535 — all confirmed.
- Descriptor 341 (0x0155): bank 0, entry offset 6437504, asset offset 7849030 (0x0077C446), format 2 ARGB4444, 67x67, encoded 8978 bytes, allocation [7849030,7858008], boundary verified, unpressed role, 1 reference.
- Descriptor 342 (0x0156): bank 0, entry offset 6437516, asset offset 7858008 (0x0077E758), format 2 ARGB4444, 67x67, encoded 8978 bytes, allocation [7858008,7866986], boundary verified, pressed role, 1 reference.
- All synthetic tests pass; py_compile passes; no forbidden files staged.
- ISP tool PE analysis: `L99 ISP V1.23.exe` (111,008 bytes, SHA-256 e8499177...) and `HFD_ISP_TOOL_V1.31.exe` (99,328 bytes, SHA-256 3fd02273...) both contain direct string refs to `/UartTFT-II_Flash.bin`, `/Flash.ini`, `/HFD_Code_V2.2.bin`, `/HFD_Code_V2.3.bin`; CRC/size/flash-ID/hardware-ID check strings present.

### Resolved blockers (C6-C18)
- C6 Updater acceptance: VERIFIED (ISP tools directly reference `/UartTFT-II_Flash.bin`) / STRONG_INFERENCE (Screen Reset EXE).
- C7 Required filename/path: VERIFIED (`UartTFT-II_Flash.bin`, root-relative alongside `Flash.ini`).
- C8 Required image size: VERIFIED (127,599,044 bytes; enforcement STRONG_INFERENCE).
- C9 UI-only vs combined write: STRONG_INFERENCE (UI-only packages confirmed; combined possible).
- C10 HFD V2.2/V2.3 selection: STRONG_INFERENCE (flash-ID `0xEFAA21` selector).
- C11 Image-level CRC: VERIFIED (CRC32 reflected IEEE per-packet; FileCRC/FlashCRC strings).
- C12 Per-packet/final verification: STRONG_INFERENCE (per-packet CRC32; final OK/fail status).
- C13 Full-image vs ranges: VERIFIED (full 127,599,044-byte image transferred).
- C14 Flash JEDEC/model checks: STRONG_INFERENCE (Flash.ini JEDEC→chip mapping; `0xEFAA21` string).
- C15 Hardware/board ID checks: STRONG_INFERENCE ("Fail to Connect a 268x device"; Qt5SerialPort VID/PID imports; `268A` string).
- C16 Version compatibility: STRONG_INFERENCE (flash-ID-based HFD selection; V1.31 unresolved).
- C17 Read-back/post-write: STRONG_INFERENCE (status strings exist; arbitrary read-back not established).
- C18 Recovery after interrupted write: UNKNOWN.

### Remaining blockers (critical)
- Image-level self-checksum within `UartTFT-II_Flash.bin`: UNKNOWN (per-packet CRC verified; image-level self-checksum not located).
- Write scope UI-only vs combined HFD_Code: STRONG_INFERENCE only.
- Recovery behavior after interrupted write: UNKNOWN.

### Safety
- Original vendor images are immutable local references.
- No firmware write from this repository is treated as safe by default.
- No unknown flash addresses, no force mode, no arbitrary erase/write replay.
- No EXE executed; no hardware accessed; no vendor binaries tracked.

## v0.1.0 - 2026-11-09

### Added
- Public project structure: README.md, CHANGELOG.md, VERSION, .gitignore, LICENSE.
- Independent protocol-analysis and replay scripts under scripts/.
- Verified notes and protocol mappings under docs/, including THIRD_PARTY_REFERENCES.md and WIN32_SERIAL_REPLAY_NOTES.md.
- Tracked data CSVs: device_mapping.csv, numpad_hid_mapping.csv, realtime_feature_report_layout.csv.

### Changed
- Converted invalid Win32 pseudo-Python into docs/WIN32_SERIAL_REPLAY_NOTES.md.
- All remaining public Python files pass py_compile.

### Verified
- Dual-controller discovery: screen EEEF:268A (CDC/serial COM port), keyboard HID 0C45:800A.
- 320x480 touchscreen resolution.
- Image upload packet structure: approximately 150 large data packets plus short commands; payload is not standard JPEG.
- Official versus custom upload timing: official approximately 1.205 seconds; Python replay substantially slower due to 64-byte pyserial pacing.
- Stable custom upload timing: 41.616 seconds with 151 ACKs; slower baseline 67.708 seconds with 150 ACKs.
- Device endpoint wedge behavior after write timeout; power cycle required before another live test.
- NumPad 17-zone HID mapping with return codes 0x0030 through 0x0040.
- Framebuffer upload separation from built-in UI: runtime photo/framebuffer upload does not overlay the built-in Mini Numpad page.
- Official reset package discovery: 2026-05-25 package recovered through the softce hash-locked offline extractor.
- Verified extraction hashes and sizes for UartTFT-II_Flash.bin, HFD_Code_V2.2.bin, HFD_Code_V2.3.bin.
- Factory UI inspection counts: 30 pages, 385 display records, 187 touch records, 1138 icon descriptors, 811 unique decoded images, 3 animations, 134 animation frames.
- Page 21 confirmation as the built-in Mini Numpad page with 11 display records and 18 touch records.
- Complete descriptor range: decimal 319 through 352 (hex 0x013F through 0x0160).
- Attribution to softce/aula-l99-research, gavindi/Aula_L99_Linux, and mos9527/evbunpack.
- Firmware safety restrictions: no unknown flash addresses, no force mode, no arbitrary erase/write replay, no universal brick-recovery claim.

### Corrected
- Obsolete README image-upload claim (standard JPEG buffer with 64-byte header) removed.
- 115200 line-coding value is not the physical USB throughput limit.
- Official upload timing corrected to approximately 1.2 seconds.

### Safety
- No hardware write performed.
- Vendor binaries, captures, dumps, decoded assets, reset ZIPs, and third-party repositories are local and ignored by Git.
- About-page V1.31 is an unresolved whole-device display version and must not be assumed to identify the screen resource image, HFD image, or PC updater.

### Known limitations
- UartTFT-II_Flash.bin role as full UI/resource image confirmed by inspection; arbitrary flash-byte read-back not established.
- ISP tool contains post-write CRC verification evidence but not arbitrary flash read-back.
- Built-in page/resource table locations within HFD_Code binaries not yet located.
- Recovery and bootloader procedure not yet established.
- Exact cause of external author's bricked keyboard remains unproven.
