# AULA L99 Project Handover

Continue this project from the verified state below. Do not restart the reverse engineering from scratch and do not repeat tests already marked verified.

## 1. Mission

Turn the AULA L99 keyboard's built-in 320x480 touchscreen into a Stream Deck-style controller: custom icons, multiple independent touch zones, PC-side actions, and dynamic status fields, while preserving the stock touch-to-keyboard logic where practical.

## 2. Current repository state

- Main repository path: C:\temp\aula-l99-controller
- Branch: main
- Remote: miniz3210/aula-l99-controller.git
- Current published release: v0.1.1
- HEAD commit: 516e3c82cdbe6c95c10ef8a92d3d7764013192d9
- Local ignored research directory: tools/softce-aula-l99-research
- Vendor binaries and extracted artifacts are local only and ignored by Git.

## 3. Verified hardware architecture

Keyboard side:
- USB HID controller: VID 0C45, PID 800A in wired mode.
- Standard keyboard HID events.
- Physical keyboard, lighting, wireless modes, and screen-to-keyboard event forwarding.
- Three-mode behavior: wired, 2.4 GHz, Bluetooth.
- Real-time telemetry uses a 64-byte HID Feature Report on Interface 3 (SET_REPORT, wValue 0x0300).
- About-page version V1.31 source unresolved.

Screen side:
- USB device: VID EEEF, PID 268A.
- Windows CDC/serial interface, typically a COM port.
- 320x480 touchscreen.
- Built-in local page and resource engine.
- LT168-family controller firmware.
- HFD executable images disassemble as little-endian M*Core per external research.

Keyboard events and screen runtime updates use different paths.

## 4. Verified public and local artifacts

Public repository files:
- README.md, CHANGELOG.md, VERSION, .gitignore, LICENSE
- scripts/ analysis and replay tools
- docs/ handover, protocol notes, firmware package map, third-party references, vendor provenance, UI-only package construction, recovery compatibility matrix, controlled flash plan, and data CSVs
- vendor/vendor_files_manifest.json — vendor file manifest (sizes and SHA-256 only; binaries not redistributed)
- docs/VENDOR_FIRMWARE_PROVENANCE.md — official firmware provenance record

Local ignored artifacts:
- tools/softce-aula-l99-research/ (softce research checkout)
- Official reset ZIP (45080624 bytes, SHA-256 e854bebb...)
- UartTFT-II_Flash.bin (127599044 bytes, SHA-256 4cb3fa5c...)
- HFD_Code_V2.2.bin (305800 bytes, SHA-256 432e358c...)
- HFD_Code_V2.3.bin (verified build): 313652 bytes, SHA-256 a76806ad...
- HFD_ISP_TOOL_V1.31.exe, Flash.ini
- Captures, dumps, decoded assets, virtual environments
- docs/UI_IMAGE_CHECKSUM_MODEL.md — checksum model of UartTFT-II_Flash.bin (image-level checksum NOT_FOUND / UNKNOWN; structured scan added in scripts/flash_checksum_scanner.py)
- docs/UI_ONLY_PACKAGE_CONSTRUCTION.md — UI-only vs combined package construction (STRONG_INFERENCE; exact accepted construction NOT verified). Exact UI-only package layout: HFD_ISP_TOOL_V1.31.exe + UartTFT-II_Flash.bin at package root; Flash.ini optional; HFD_Code files can be omitted.
- docs/VENDOR_FIRMWARE_PROVENANCE.md — official firmware provenance (listing URL, direct ZIP URL, filename, size, SHA-256, URL directory date != release date, ZIP can reproduce UartTFT-II_Flash.bin via hash-locked extractor, private backup recommendation, no vendor binaries redistributed)
- docs/RECOVERY_COMPATIBILITY_MATRIX.md — recovery and package compatibility matrix (interrupted-write recovery: automatic UNKNOWN, manual re-entry STRONG_INFERENCE)
- docs/CONTROLLED_FLASH_PLAN.md — controlled flash plan (UI-only package layout included)
- docs/PAGE21_FIRST_PATCH_PLAN.md — Page 21 return code 0x003B, descriptor 341/342 patch plan. Equal-size (8,978-byte) in-place replacement is structurally sufficient: no descriptor-table, page-table, touch-record, global-metadata, or per-resource-checksum changes required. Image-level checksum blocker remains open.

External third-party repositories (not vendored):
- https://github.com/softce/aula-l99-research
- https://github.com/gavindi/Aula_L99_Linux
- https://github.com/mos9527/evbunpack

Same-named firmware files may contain different builds and must be identified by hash, not filename.

## 5. Verified screen upload protocol

- Official captured photo upload contains 154 logical chunks.
- Four are short control or commit commands.
- Total captured stream is approximately 309071 bytes.
- The screen acknowledges packet transfers.
- Upload targets photo/background/GIF flash slots.
- Upload does not overlay the built-in Mini Numpad page.
- The image payload is not standard JPEG. Obsolete JPEG/64-byte-header claims are removed.
- ACK does not prove address safety.

## 6. Verified performance evidence

- Official application: approximately 1.205 seconds, 150 x 2060-byte USB Bulk OUT transfers.
- Current Python replay: stable verified run 41.616 seconds with 151 ACKs; slower baseline 67.708 seconds with 150 ACKs.
- Root cause: current replay splits each 2060-byte logical packet into approximately 33 synchronous 64-byte pyserial writes, each artificially paced.
- The 115200 CDC line-coding value is not a reliable physical throughput limit for this USB bulk implementation.
- Write timeout leaves the endpoint wedged; a device power cycle is required before another live test.
- Next transport: scripts/replay_captured_screen_win32.py with native Windows overlapped I/O, complete 2060-byte logical packets, asynchronous ACK reads, no USB driver replacement, no Zadig/WinUSB/libusbK in the first implementation.

## 7. Verified factory resource image

- Extraction source: official AULA reset package dated 2026-05-25, recovered via the softce hash-locked offline extractor.
- Verified by size and SHA-256 against the research repository documentation.
- Inspector results: 30 pages, 385 display records, 187 touch records, 1138 icon descriptors, 811 unique decoded images, 3 animations, 134 animation frames.
- Manifest records 26 wider-image decode issues, primarily invalid-bounds descriptor candidates.
- Page 21 rendered successfully as the factory Mini Numpad page.
- Limitation: this is the screen resource image, not a raw NAND dump; it does not include verified per-device OOB, ECC, bad-block, calibration, or unique-board data.

## 8. Page 21 Mini Numpad

Page 21 has 11 display records and 18 touch records. Seventeen are type 0xC001 action records; one is a type 0x8001 Home/back navigation record.

Home/back: return value 0x0020, goto page 1. NumPad actions: goto_page 65535. Descriptor range: decimal 319 through 352 (hex 0x013F through 0x0160).

| Command | Button | Rectangle [x1,y1,x2,y2] | Normal/Pressed icons |
|---------|--------|-------------------------|----------------------|
| 0x0030 | Num | [13,115,79,181] | 319/320 |
| 0x0031 | Divide | [89,115,155,181] | 321/322 |
| 0x0032 | Multiply | [165,115,231,181] | 323/324 |
| 0x0033 | Minus | [243,115,309,181] | 325/326 |
| 0x0034 | NumPad 7 | [13,190,79,256] | 327/328 |
| 0x0035 | NumPad 8 | [89,190,155,256] | 329/330 |
| 0x0036 | NumPad 9 | [165,190,231,256] | 331/332 |
| 0x0037 | Plus | [243,190,309,327] | 333/334 |
| 0x0038 | NumPad 4 | [13,263,79,329] | 335/336 |
| 0x0039 | NumPad 5 | [89,263,155,329] | 337/338 |
| 0x003A | NumPad 6 | [165,263,231,329] | 339/340 |
| 0x003B | NumPad 1 | [13,337,79,403] | 341/342 |
| 0x003C | NumPad 2 | [89,337,155,403] | 343/344 |
| 0x003D | NumPad 3 | [165,337,231,403] | 345/346 |
| 0x003E | Enter | [243,337,309,474] | 351/352 |
| 0x003F | NumPad 0 | [13,407,150,473] | 347/348 |
| 0x0040 | Decimal/Delete | [165,407,231,473] | 349/350 |

The 17 buttons use 34 normal/pressed icon descriptors.

### 8a. Descriptor 341 / 342 mapping (verified via scripts/inspect_l99_descriptor.py)

Descriptor 341 (0x0155) — NumPad 1 unpressed:
- Icon table bank: 0
- Descriptor table base / file offset: 6433412 (0x00623114)
- Exact descriptor entry file offset: 6437504 (0x00623A80)
- Raw descriptor bytes: 46c477004300430012230002
- Descriptor entry length: 12
- Source asset logical address / file offset: 7849030 (0x0077C446) — direct file offset, no translation
- Encoded format number: 2 — ARGB4444 (raw 16-bit packed)
- Decoded dimensions: 67 x 67
- Encoded payload length: 8978 bytes
- Full encoded record length (incl. header): 8990 bytes
- Encoded range: [7849030, 7858008] (0x0077C446 .. 0x0077E758)
- Allocation: start 7849030, end 7858008, capacity 8978
- Next confirmed asset boundary: 7858008 — VERIFIED (next descriptor address == end)
- Boundary confidence: verified
- Decoded asset: inspection\assets\0077C446_67x67_f2.png
- Decoded PNG SHA-256: daddc6dc21c58d2bbd1597024113afb2b38472d14baa239af59f8fae29c0e99b
- Source encoded-byte SHA-256: 785416bcad1789248b62dfc085f477806547d5c01f747dde150f9555a2c70317
- Referencing records: 1 — page 21 touch record offset 150697, role unpressed, return 0x003B, goto_page 65535
- Shared by other pages/controls: No
- Manifest decode issues: 0

Descriptor 342 (0x0156) — NumPad 1 pressed:
- Icon table bank: 0
- Descriptor table base / file offset: 6433412 (0x00623114)
- Exact descriptor entry file offset: 6437516 (0x00623A8C)
- Raw descriptor bytes: 58e777004300430012230002
- Descriptor entry length: 12
- Source asset logical address / file offset: 7858008 (0x0077E758) — direct file offset, no translation
- Encoded format number: 2 — ARGB4444 (raw 16-bit packed)
- Decoded dimensions: 67 x 67
- Encoded payload length: 8978 bytes
- Full encoded record length (incl. header): 8990 bytes
- Encoded range: [7858008, 7866986] (0x0077E758 .. 0x00780A6A)
- Allocation: start 7858008, end 7866986, capacity 8978
- Next confirmed asset boundary: 7866986 — VERIFIED (next descriptor address == end)
- Boundary confidence: verified
- Decoded asset: inspection\assets\0077E758_67x67_f2.png
- Decoded PNG SHA-256: aef08b1f04064c2a651b9db115d019c33425d8716fe3cc2a8ec6216d36c43750
- Source encoded-byte SHA-256: 4265cf743061b87fb85479bc64df1d05d241b1aaf88ea51392f01e2781332474
- Referencing records: 1 — page 21 touch record offset 150697, role pressed, return 0x003B, goto_page 65535
- Shared by other pages/controls: No
- Manifest decode issues: 0

Patch feasibility: PROVEN_FOR_OFFLINE_WORKING_COPY (exact encoded range, exact verified allocation
boundary, established format, confirmed dimensions, single known reference, replacement-size limit =
allocation capacity 8978, no overlap with adjacent asset). Metadata/checksum implications remain
Unknown (not covered by manifest). In-place replacement is not declared safe unless all of these are
established and a working-copy patch is validated.

## 9. Version ambiguity

- Device About page displays AULA L99 V1.31.
- Source of V1.31 is not proven.
- It may be keyboard MCU, screen MCU, UI/project version, or whole-device product version.
- HFD_ISP_TOOL_V1.31.exe version must not be equated automatically with the About-page version.
- HFD_Code V2.2/V2.3 names are separate version domains.
- Firmware compatibility must be based on screen-side identifiers, hashes, layout, and official package targeting.

## 10. What has been disproved or corrected

- The image stream is not standard JPEG.
- The 115200 line-coding value is not the observed USB transfer throughput limit.
- Official upload is approximately 1.2 seconds, not 30 to 40 seconds.
- Framebuffer upload does not overlay the Mini Numpad page.
- The external 2026-05-25 reset package contains the complete known UI/resource update image.
- About-page V1.31 is not proven to be a screen firmware version.
- Acknowledgement does not establish flash address safety.
- check_upload_fits() is not a universal allowlist and can be bypassed or fail open for unknown addresses depending on the caller.
- The exact cause of the external author's bricked keyboard remains unproven.

## 11. Safety constraints

- Original vendor images are immutable local references.
- No firmware write from this repository MUST be treated as safe by default.
- NO unknown flash addresses.
- NO force mode.
- NO arbitrary erase/write replay.
- NO firmware update during extraction or inspection.
- NO claim of universal brick recovery.
- Hardware writes are BLOCKED pending offline patch validation and recovery review.
## 12. Immediate next milestone

### 12a. Controlled flash plan — offline static analysis (COMPLETE)

Offline static analysis of the three updater candidates (`L99 ISP V1.23.exe`, `HFD_ISP_TOOL_V1.31.exe`,
Screen Reset EXE) has been completed without executing any EXE or connecting hardware. Results are documented
in `docs/CONTROLLED_FLASH_PLAN.md` and `docs/RECOVERY_COMPATIBILITY_MATRIX.md`.

Key resolved findings:
- C6 Updater acceptance: **VERIFIED** for both ISP tools (direct string ref `/UartTFT-II_Flash.bin`); STRONG_INFERENCE for Screen Reset EXE.
- C7 Filename/path: **VERIFIED** (`UartTFT-II_Flash.bin`, root-relative alongside `Flash.ini`).
- C8 Size: **VERIFIED** (127,599,044 bytes).
- C11 CRC: **VERIFIED** (CRC32 reflected IEEE per-packet; FileCRC/FlashCRC strings).
- C13 Transmission scope: **VERIFIED** (full 127,599,044-byte image transferred).
- C9 UI-only vs combined HFD write: STRONG_INFERENCE (UI-only packages confirmed; combined possible). Exact UI-only package construction NOT verified.
- C10 HFD V2.2/V2.3 selection: STRONG_INFERENCE (flash-ID `0xEFAA21` selector).
- C14 Flash-ID/JEDEC: STRONG_INFERENCE (Flash.ini JEDEC→chip mapping).
- C15 Hardware-ID: STRONG_INFERENCE ("Fail to Connect a 268x device"; Qt5SerialPort VID/PID imports).
- C16 Image-level self-checksum: UNKNOWN (per-packet CRC verified; image-level self-checksum not located).
- C17 Post-write read-back: STRONG_INFERENCE (status strings exist; arbitrary read-back not established).
- C18 Recovery after interrupted write: UNKNOWN.
- UI-only package layout: HFD_ISP_TOOL_V1.31.exe + UartTFT-II_Flash.bin at package root; Flash.ini optional; HFD_Code files can be omitted (STRONG_INFERENCE).
- HFD write order before/after UI: UNKNOWN.
- Interrupted update can re-enter ISP: manual re-entry STRONG_INFERENCE; automatic recovery UNKNOWN.

**Decision: NO-GO.** No hardware write is permitted until all critical blockers are VERIFIED:
1. Image-level self-checksum requirement.
2. Write scope confirmed as VERIFIED.
3. Recovery behavior after interrupted write determined.
4. Exact UI-only package acceptance VERIFIED.

Next task: Resolve remaining critical blockers offline (image-level self-checksum, write scope, interrupted-write recovery, exact UI-only package acceptance). Do not execute any EXE or connect hardware.

### 12b. Offline NumPad icon patcher (scripts/patch_l99_numpad_icon.py)

Already complete; see prior sections for details.

### 12c. Official update capture toolkit (ADDED in v0.6.0)

Capture preparation only — no updater execution, no hardware access, no flashing.
Decision remains NO-GO.

- `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md` — capture procedure answering ten questions static analysis cannot verify (files opened, HFD V2.2/V2.3 read, UartTFT-II_Flash.bin read, file/USB order, UI vs HFD payloads, bytes per payload, re-enumeration/ISP entry, FileCRC/FlashCRC, success/restart).
- `scripts/prepare_official_capture.ps1` — verifies official file hashes, absence of patched_UartTFT-II_Flash.bin, no updater running, no tracked vendor/capture files over 5 MB.
- `scripts/analyse_official_capture.py` — offline analyser for exported Procmon CSV + USBPcap/Wireshark PCAPNG; marks every finding EVIDENCE or INFERENCE; never opens COM/USB, never executes an updater.
- `tests/test_analyse_official_capture.py` — synthetic analyser tests (no vendor firmware, no hardware).

Validation: PowerShell syntax check, py_compile, `python -m unittest discover -s tests`, `git diff --check`, no vendor/capture/generated files tracked, no staged file over 5 MB.

## 13. Acceptance criteria

Offline patcher:
- Factory source unchanged.
- Separate output file.
- Only intended asset bytes and required metadata changed.
- No touch record changes.
- Inspector still parses Page 21.
- All 17 actions remain mapped.
- Replacement allocation is in bounds.
- SHA-256 and diff report generated.

Win32 uploader:
- Compiles or passes py_compile as applicable.
- Does not split logical packets in userland unless required by Win32.
- Preserves command ordering.
- Receives expected ACK count.
- Handles cancellation safely.
- Reports exact failing packet and offset.
- Never retries automatically after timeout.
- Requires explicit power cycle after endpoint wedge.
- Initial target under 10 seconds.
- Final target close to official 1 to 2 seconds.

## 14. Known external references

- softce/aula-l99-research — verified factory reset extraction offsets, hash-locked extractor, UI parser, page/resource research, demonstrated custom UI approach.
- gavindi/Aula_L99_Linux — extensive keyboard and screen protocol research, Linux tools, captures, upload format work; protocol baseline for general photo/GIF/RTC/audio-spectrum work.
- mos9527/evbunpack — Enigma Virtual Box extraction used to inspect the official updater container.

Neither third-party tree is committed to this project, and third-party firmware or artwork is not licensed by this repository.

## 15. Resume commands

Run each as a simple PowerShell command or a complete script block. Do not split if/else across interactive lines.

cd "C:\temp\aula-l99-controller"

git status
git branch --show-current
git remote -v
git log --oneline --decorate -5

ii tools/softce-aula-l99-research

Get-Content tools/softce-aula-l99-research/inspection/page21_summary.json

ii tools/softce-aula-l99-research/inspection/pages/page_21_bank0.png
ii tools/softce-aula-l99-research/inspection/pages/page_21_bank1.png

py -m pytest

Get-FileHash tools/softce-aula-l99-research/input/L99-reset.zip -Algorithm SHA256
Get-FileHash tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin -Algorithm SHA256
Get-FileHash tools/softce-aula-l99-research/extracted/HFD_Code_V2.2.bin -Algorithm SHA256
Get-FileHash tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin -Algorithm SHA256

cd "C:\temp\aula-l99-controller"

## 16. Checksum scanner operation and performance

`scripts/flash_checksum_scanner.py` is the offline, read-only image-level
self-checksum scanner for `UartTFT-II_Flash.bin`. It never modifies its input.

### Why the original deep scan took approximately 30 to 40 minutes

The previous implementation ran a whole-image CRC16/MODBUS and CRC32/standard
over the full 127,599,044-byte image for every candidate field offset inside
each region, recomputing whole-region checksums repeatedly in Python. It was
effectively single-threaded: it used one logical processor on the AMD Ryzen 9
5900HX (8 cores / 16 logical processors), so roughly one CPU was doing all the
work. Combined with repeated full-image copies, that produced the 30-40 minute
runtime.

### Quick versus deep mode

- `--mode quick`: targeted structural checks only. Verifies source hashes,
  known structural regions, changed-range containment, known headers/tables/
  trailers, and descriptor 341/342 areas. No exploratory whole-image candidate
  scanning. Target runtime under 30 seconds on the current image (measured
  ~2.3 seconds on the 127,599,044-byte factory image). Whole-image checks use
  fast/native algorithms (zlib CRC32, additive sums) to stay within budget.
- `--mode deep`: full structural investigation over all fixed-structure
  regions using all algorithms. Results are cached so identical inputs return
  immediately.

### Cache-key fields

The deep-mode cache key is a SHA-256 over:
- factory SHA-256,
- patched SHA-256,
- scanner version (`SCANNER_VERSION`),
- scanner source SHA-256,
- algorithm list,
- region-map SHA-256.

Any change to these inputs invalidates the cache and forces a re-run.

### Native CRC, multiprocessing, mmap/memoryview requirements

- Native C-backed CRC32 via `zlib.crc32` where mathematically equivalent and
  verified against golden vectors (`123456789 -> 0xCBF43926`).
- Lookup-table CRC16/MODBUS and CRC32/standard implementations.
- Regions are parallelised across worker processes with
  `ProcessPoolExecutor` (never `ThreadPoolExecutor` for CPU-bound work).
- Default worker count: `min(8, physical CPU cores)` (Ryzen 9 5900HX has 8
  cores; Python uses one logical processor unless multiprocessed).
- Each image is read once; workers read only their assigned byte range from
  disk so the full image is never pickled across process boundaries.
- Each algorithm is calculated once per structural region; calculated values
  are compared only against structurally plausible field offsets (no
  birthday-paradox "value appears anywhere" scanning).
- No GPU support.

### Quick-mode target under 30 seconds

Quick mode must complete well under 30 seconds on the current image so it can
be used for normal validation and release checks.

### Deep scan should run only when source or scanner inputs change

Deep mode re-runs only when the cache key changes (factory hash, patched hash,
scanner version, scanner source hash, algorithm list, or region map). A valid
cache hit returns instantly.

### Current image-checksum classification is UNKNOWN

The structured scan over all fixed-structure regions found no stored field at
any plausible offset matching any tested algorithm. Classification: UNKNOWN.
Lack of a match is not proof of absence.

### False-positive CRC16 matches are not evidence

CRC16 matches found in large regions were statistical collisions, not
checksum evidence. Birthday-paradox matches are deliberately not reported.

### Current decision remains NO-GO

No hardware write is permitted until all critical blockers (image-level
self-checksum, write scope, interrupted-write recovery) are VERIFIED.

### Exact resume commands

Quick mode:
```
cd "C:\temp\aula-l99-controller"
python scripts/flash_checksum_scanner.py tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin --factory tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin --mode quick
```

Cached deep mode (runs only if source/scanner inputs changed; cache hit returns immediately):
```
cd "C:\temp\aula-l99-controller"
python scripts/flash_checksum_scanner.py tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin --factory tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin --patched <patched_image.bin> --mode deep
```

Prints phase name, progress, elapsed time, full-image pass count, worker count,
and cache hit/miss. A configurable `--max-runtime` guard stops deep mode cleanly.
