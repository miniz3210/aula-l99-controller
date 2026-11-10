# Changelog

## Unreleased

### Added
- Consolidated project documentation: README.md, docs/PROJECT_HANDOVER.md, CHANGELOG.md.
- Documented verified factory UI inspection counts and Page 21 Mini Numpad 17-zone map.
- Documented verified screen upload protocol: 154 chunks, 150 x 2060-byte packets, four short commands.
- Documented verified upload performance: official ~1.205 s vs current Python replay 41.616 s / 67.708 s.
- Documented next transport milestone: scripts/replay_captured_screen_win32.py with native Windows overlapped I/O.
- Documented safety constraints and version ambiguity (About-page V1.31 unresolved).

### Changed
- Replaced repetitive changelog with curated release entries.
- Removed obsolete image upload claim (standard JPEG with 64-byte header).
- Removed unproven claims about firmware safety and universal recovery.

### Fixed
- Corrected protocol history: 115200 CDC line-coding is not the observed USB transfer throughput limit.
- Corrected upload timing: official upload is ~1.2 seconds, not 30 to 40 seconds.

### Verified
- Factory reset ZIP: 45080624 bytes, SHA-256 e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3.
- UartTFT-II_Flash.bin: 127599044 bytes, SHA-256 4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4.
- HFD_Code_V2.2.bin: 305800 bytes, SHA-256 432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf.
- HFD_Code_V2.3.bin: 313652 bytes, SHA-256 a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03.

### Safety
- Original vendor images are immutable local references.
- No firmware write from this repository is treated as safe by default.
- No unknown flash addresses, no force mode, no arbitrary erase/write replay.

### Next
- Resolve descriptor 341/342 to source offsets, formats, dimensions, and allocations.
- Build offline-only single-button patcher.
- Implement native Win32 overlapped uploader.

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
