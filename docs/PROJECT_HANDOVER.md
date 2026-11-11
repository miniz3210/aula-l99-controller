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

### 12c. Official update capture toolkit (ADDED in v0.6.0; corrected to L99 ISP V1.23.exe in v0.6.1)

Capture preparation only — no updater execution, no hardware access, no flashing.
Decision remains NO-GO.

The only approved capture target is the original untouched L99 ISP V1.23.exe package
(`firmware\unpacked\L99 ISP V1.23.exe`, 111,008 bytes,
SHA-256 `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0`).

Excluded targets: Screen Reset EXE from L99-reset.zip, patched_UartTFT-II_Flash.bin,
renamed/replaced vendor payloads, and new UI-only package construction.

- `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md` — capture procedure answering ten questions static analysis cannot verify (files opened, HFD V2.2/V2.3 read, UartTFT-II_Flash.bin read, file/USB order, UI vs HFD payloads, bytes per payload, re-enumeration/ISP entry, FileCRC/FlashCRC, success/restart). Records the L99 ISP V1.23.exe package path, filename, size and SHA-256, inventories every file beside the EXE, rejects excluded targets, generates Procmon filters for the real EXE and expected child processes, and instructs how to identify the USB controller for EEEF:268A.
- `scripts/prepare_official_capture.ps1` — preflight-only command (`-Preflight`) that performs no hardware access, launches no EXE, verifies package hashes, verifies Procmon/Wireshark/USBPcap availability, verifies free disk space, creates an empty timestamped capture directory, prints READY or NOT READY.
- `scripts/analyse_official_capture.py` — offline analyser for exported Procmon CSV + USBPcap/Wireshark PCAPNG; marks every finding EVIDENCE or INFERENCE; never opens COM/USB, never executes an updater; detects process/child-process names without launching; generates Procmon filters.
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

## 17. Current baseline

Product: Chinese AULA L99 version 1.0.1.4
Install directory: C:\Program Files (x86)\AULA L99
Baseline inventory: C:\temp\L99_1.0.1.4_baseline.txt
Files inventoried: 212
Main application: DeviceDriver.exe — 1,837,056 bytes, SHA-256 DD9C934E2F6F1CC53AE4AFB5B412C3F696CD4D329A03DF28BD151DAB90B3E6B3
Process Monitor confirmed that Explorer launched DeviceDriver.exe and that DeviceDriver.exe launched both firmware tools.

Chinese version 1.0.1.4 is the analysis baseline because it is currently the only available version known to expose both keyboard firmware upgrade and screen firmware upgrade. These must always be treated as separate upgrade paths targeting different controllers. Do not compare the keyboard updater version and the screen updater version as if they are part of one version sequence.

## 18. Verified controller and updater separation

Keyboard firmware upgrade — verified by separate Process Create and Process Start captures, not a filename-based assumption:
- Parent: DeviceDriver.exe
- Child: C:\Program Files (x86)\AULA L99\firmware\L99_中文_V1.31.exe — 2,213,280 bytes, SHA-256 E316C25591711D1B425E0BB4F17C02813E70AB9D8CD982D91EA331222112276D
- Target path: keyboard firmware/controller path; known keyboard controller: USB HID 0C45:800A

Screen firmware upgrade — verified by separate Process Create and Process Start captures, not a filename-based assumption:
- Parent: DeviceDriver.exe
- Child: C:\Program Files (x86)\AULA L99\firmware\L99_ISP_中文完整UI_V1.23_156.exe — 162,852,672 bytes, SHA-256 0A77055429DA60E35AFE419A367BE1AB987B7E3F4CA3B67477BD017AA097FC55
- Target path: screen firmware/ISP path; known screen interface: EEEF:268A virtual COM; known screen controller family under investigation: LT268A/LT2686 UartTFT

Keyboard controller firmware and screen-controller firmware are distinct upgrade paths and must never be merged.

## 19. Verified file identities

- DeviceDriver.exe: 1,837,056 bytes, SHA-256 DD9C934E2F6F1CC53AE4AFB5B412C3F696CD4D329A03DF28BD151DAB90B3E6B3
- L99_中文_V1.31.exe: 2,213,280 bytes, SHA-256 E316C25591711D1B425E0BB4F17C02813E70AB9D8CD982D91EA331222112276D
- L99_ISP_中文完整UI_V1.23_156.exe: 162,852,672 bytes, SHA-256 0A77055429DA60E35AFE419A367BE1AB987B7E3F4CA3B67477BD017AA097FC55
- HFD_ISP_TOOL_V1.31.exe: 99,328 bytes, SHA-256 3FD0227368539E4B80A385EA721A1F091D6F22997DA24451E2F8248D512CA282; matching copies exist under evbunpack_output and firmware\unpacked
- HFD_Code_V2.2.bin: 305,800 bytes, SHA-256 432E358CAC96FB930AB680ADA6F953C9005027C58B31B7EE3BB6BC7868EF35CF; matching copies exist under evbunpack_output, firmware\unpacked, and the local softce working tree
- Chinese 1.0.1.4 HFD_Code_V2.3.bin variant: 313,504 bytes, SHA-256 B277823234FCAB7137963896493BCB6896FD985FC972354166FCFC584534E37F
- Other local HFD_Code_V2.3.bin variant: 313,652 bytes, SHA-256 A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03
- Flash.ini: 1,571 bytes, SHA-256 E515905C61A6AD99BF96EAAC3E24E5CFD21E274C087F9903B14F35ECECE21E2C — flash-chip geometry database (JEDEC IDs, page sizes, page/block counts, chip models for Winbond, GigaDevice, XTX, Macronix, and related devices); contains no firmware filenames, no HFD selection logic, no UartTFT-II_Flash.bin selection logic, no L99 model mapping, no destination addresses, no version-selection rules; not a payload-selection configuration
- UartTFT-II_Flash.bin: 127,599,044 bytes, SHA-256 4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4

Same-named firmware files may contain different builds and must be identified by hash, not filename. The two V2.3 files are genuinely different builds/variants: size difference 148 bytes, common prefix 0 bytes, first difference at offset 0x0, differing offsets in overlapping range 286084, common suffix 22 bytes.

## 20. Official UartTFT-II_Flash.bin provenance

- File: UartTFT-II_Flash.bin
- Size: 127,599,044 bytes
- SHA-256: 4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4
- Size (hexadecimal): 0x079B01C4
- Provenance: downloaded directly from the official AULA website during the initial research.
- Current local working path: tools\softce-aula-l99-research\extracted\UartTFT-II_Flash.bin (working location only; not file provenance).

It was not extracted from the softce repository, not distributed by the softce repository, not extracted from the Chinese 1.0.1.4 updater, not produced by evbunpack, and not recovered from a process memory dump. The directory path under the softce working tree must not be interpreted as file provenance. The website URL and exact download timestamp are not known from repository artifacts and must not be claimed.

Provenance wording conflict: softce documentation describes its hash-matching copy as extracted from a 2026.5.25 reset package. Matching SHA-256 confirms byte identity between the two accounts but does not prove identical provenance. This is a provenance wording conflict, not a structural-data conflict.

## 21. Completed work

- Chinese 1.0.1.4 selected as the baseline.
- Complete 212-file installed-directory inventory created.
- Main executable identified and hashed.
- Keyboard and screen upgrade UI entries mapped to their real child executables.
- Both updater executables sized and hashed.
- Screen updater launch-only behavior inspected without pressing Start.
- EVB-style temporary PE stubs preserved and inspected.
- Existing extracted ISP tool, V2.2, V2.3, and Flash.ini inventoried.
- Flash.ini purpose identified as a flash-chip geometry database.
- Two V2.3 variants compared and proven substantially different.
- Official UartTFT-II_Flash.bin provenance corrected to an official AULA website download.
- Raw full-file containment test performed against the Chinese 1.0.1.4 screen updater: FULL_RAW_MATCH: NO.
- No firmware flash or intentional write performed during this work.

## 22. Key findings

- Keyboard and screen updater mappings are verified by Process Create and Process Start captures; they are not filename-based assumptions. Keyboard targets USB HID 0C45:800A; screen targets EEEF:268A virtual COM (LT268A/LT2686 UartTFT family under investigation).
- The screen updater was launched without pressing its Start button. Nineteen evb*.tmp files were preserved, each exactly 1536 bytes, each beginning with an MZ header, with strings including "This program must be run under Win32", "ntdll.dll", and "ZwOpenFile"; all nineteen had different SHA-256 hashes. They are small PE/helper stubs, not complete screen firmware payloads.
- Flash.ini is a flash-chip geometry database, not a payload-selection configuration.
- The two HFD_Code_V2.3.bin variants are genuinely different builds (148-byte size difference; 0-byte common prefix; first difference at offset 0x0; 286084 differing offsets in overlapping range; 22-byte common suffix).
- The official UartTFT-II_Flash.bin is not stored verbatim as one contiguous uncompressed block inside the Chinese 1.0.1.4 screen updater (raw containment test: FULL_RAW_MATCH: NO). Possible explanations (compressed or encrypted storage, Enigma virtual-file packaging, segmented storage, runtime reconstruction, different official builds) remain unproven.
- UartTFT-II_Flash.bin is an official AULA website download; its current path under the softce working directory conveys no provenance.

## 23. Important corrections

- UartTFT-II_Flash.bin provenance: official AULA website download, not a softce repository file, not distributed by softce, not extracted from the Chinese 1.0.1.4 updater, not produced by evbunpack, and not recovered from a process memory dump. The path tools\softce-aula-l99-research\extracted\UartTFT-II_Flash.bin is only a local working location.
- The two HFD_Code_V2.3.bin files are different builds/variants, not one file with a simple 148-byte trailer.
- Flash.ini is not a payload-selection configuration.

## 24. Unresolved questions

1. Determine the exact structural relationship between the official UartTFT-II_Flash.bin and the Chinese 1.0.1.4 screen updater.
2. Determine whether the updater contains the same logical full-flash content in compressed, encrypted, segmented, virtualized, or reconstructed form.
3. Identify which screen-controller firmware component is represented by HFD_Code_V2.2.bin, Chinese 1.0.1.4 HFD_Code_V2.3.bin, and the other V2.3 variant.
4. Determine how HFD_ISP_TOOL_V1.31.exe selects a firmware payload.
5. Identify the exact flash layout and resource-region boundaries inside the official UartTFT-II_Flash.bin.
6. Separate executable screen-controller firmware from UI resources, page descriptions, images, fonts, language assets, and touch-zone records.
7. Determine whether a verified read-back and recovery path exists before any modified image is written.
8. Preserve the distinction between keyboard controller firmware, screen-controller executable firmware, full screen flash/resource image, normal photo-frame framebuffer upload, and HID Feature Report updates used by built-in widgets.

## 25. Do not repeat

A new chat must not repeat the following unless new evidence makes it necessary:

- baseline inventory
- updater SHA256 collection
- Process Monitor child-process mapping
- launch-only screen updater capture
- generic strings scan of the 162 MB updater
- idle memory dump
- generic Enigma detection
- extraction of HFD_ISP_TOOL_V1.31.exe
- extraction of HFD_Code_V2.2.bin
- extraction of the local Chinese 1.0.1.4 HFD_Code_V2.3.bin
- analysis of Flash.ini as a chip database
- comparison proving that the two V2.3 files are different
- raw full-file search for UartTFT-II_Flash.bin inside the updater
- investigation of the nineteen 1536-byte evb*.tmp files as possible firmware payloads
- attempts to prove UartTFT-II_Flash.bin provenance from its current softce working-directory path

## 26. Safety constraints

- Firmware work remains read-only.
- Do not press Start in either updater.
- Do not flash either HFD_Code_V2.3.bin variant.
- Do not write the official UartTFT-II_Flash.bin.
- Do not enter bootloader mode solely for experimentation.
- Do not replay upgrade traffic.
- Do not modify updater executables.
- Do not treat the existence of an official image as proof that recovery is safe.
- Brick risk remains material until flash layout, validation logic, write sequence, and recovery method are verified.

## 27. Next planned task

Read-only analysis of the native dynamic widget model, focusing on display type 3 variable-to-icon selection and display type 5 animation behavior, to determine whether Page 21 can support Stream Deck-style runtime state feedback without changing touch records or repeatedly writing resource flash.

Later analysis should determine:
- runtime variable addresses used by type 3 widgets
- icon-range selection behavior
- min/max value behavior
- existing pages that demonstrate runtime icon switching
- type 5 start, stop, loop, and frame-selection behavior
- whether Page 21 can reuse an existing volatile RAM variable
- whether Companion feedback can be mapped to native L99 icon states

Do not begin this dynamic-widget task now.

## 28. Scanner performance requirements

If new scanning code is required, it must include:

- quick and deep modes
- a quick-mode target under 30 seconds
- a deep-result cache keyed by source hash, patched hash when applicable, scanner version, algorithms, and region map
- native CRC implementations
- multiprocessing across independent jobs
- no full-region rescan for every candidate
- mmap or memoryview access
- progress reporting
- phase timings
- deterministic machine-readable output

These scanner requirements and current findings must also remain recorded in docs/PROJECT_HANDOVER.md for new-chat continuity.

## 29. New-chat starting prompt

Paste the following into a new chat:

```
Read docs/PROJECT_HANDOVER.md first, then read the latest CHANGELOG.md entry. Preserve all verified findings: Chinese AULA L99 version 1.0.1.4 is the analysis baseline (install directory C:\Program Files (x86)\AULA L99, 212-file inventory at C:\temp\L99_1.0.1.4_baseline.txt, DeviceDriver.exe 1,837,056 bytes SHA-256 DD9C934E2F6F1CC53AE4AFB5B412C3F696CD4D329A03DF28BD151DAB90B3E6B3). Keep keyboard and screen firmware upgrade paths strictly separate; they target different controllers and are not one version sequence.

Verified identities to preserve: DeviceDriver.exe SHA-256 DD9C934E2F6F1CC53AE4AFB5B412C3F696CD4D329A03DF28BD151DAB90B3E6B3; keyboard updater L99_中文_V1.31.exe (2,213,280 bytes, SHA-256 E316C25591711D1B425E0BB4F17C02813E70AB9D8CD982D91EA331222112276D, USB HID 0C45:800A); screen updater L99_ISP_中文完整UI_V1.23_156.exe (162,852,672 bytes, SHA-256 0A77055429DA60E35AFE419A367BE1AB987B7E3F4CA3B67477BD017AA097FC55, EEEF:268A virtual COM, LT268A/LT2686 UartTFT family under investigation); HFD_ISP_TOOL_V1.31.exe SHA-256 3FD0227368539E4B80A385EA721A1F091D6F22997DA24451E2F8248D512CA282; HFD_Code_V2.2.bin SHA-256 432E358CAC96FB930AB680ADA6F953C9005027C58B31B7EE3BB6BC7868EF35CF; the two HFD_Code_V2.3.bin variants B2778232... (313,504 bytes) and A76806AD... (313,652 bytes) are genuinely different builds; Flash.ini SHA-256 E515905C61A6AD99BF96EAAC3E24E5CFD21E274C087F9903B14F35ECECE21E2C is a flash-chip geometry database, not a payload-selection configuration.

UartTFT-II_Flash.bin (127,599,044 bytes, SHA-256 4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4) was downloaded directly from the official AULA website during initial research. Its current local path tools\softce-aula-l99-research\extracted\UartTFT-II_Flash.bin is only a working location, not provenance. Do not claim it came from softce or evbunpack, and do not claim the website URL or download timestamp is known. Raw containment test inside the Chinese 1.0.1.4 screen updater returned FULL_RAW_MATCH: NO; explanations remain unproven.

Keep all work read-only. Do not press Start in either updater. Do not flash either HFD_Code_V2.3.bin variant. Do not write the official UartTFT-II_Flash.bin. Do not enter bootloader mode for experimentation. Do not replay upgrade traffic. Do not modify updater executables.

Do not repeat completed work unless new evidence requires it: baseline inventory, updater SHA256 collection, Process Monitor child-process mapping, launch-only screen updater capture, generic strings scan of the 162 MB updater, idle memory dump, generic Enigma detection, extraction of HFD_ISP_TOOL_V1.31.exe, extraction of HFD_Code_V2.2.bin, extraction of the local Chinese 1.0.1.4 HFD_Code_V2.3.bin, Flash.ini chip-database analysis, V2.3 difference comparison, raw full-file search for UartTFT-II_Flash.bin inside the updater, investigation of the nineteen 1536-byte evb*.tmp files as firmware payloads, or provenance claims from the softce working-directory path.

Begin with read-only structural analysis of the official UartTFT-II_Flash.bin to produce a verified region map (offsets, lengths, signatures or magic values, image/resource regions, page-description records, touch-record areas, string/font/language regions, executable-code candidates, checksums or validation fields, erased or padding regions). Inspect existing softce repository documentation and tools for commands that already parse UartTFT-II_Flash.bin before creating new scripts; exclude .venv, __pycache__, node_modules, binary captures, large dumps, and generated output directories from broad searches. Present the next command before moving forward. Explicitly distinguish facts, hypotheses, and unverified assumptions in every response.
```

## 30. Corrected structural findings — UartTFT-II_Flash.bin (independently reviewed and corrected)

### Source identity and provenance

- Official UartTFT-II_Flash.bin
- Size: 127,599,044 bytes
- Hexadecimal size: 0x079B01C4
- SHA-256: 4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4
- Current local working path: tools\softce-aula-l99-research\extracted\UartTFT-II_Flash.bin (working location only; not file provenance).
- Provenance wording conflict: softce documentation describes its hash-matching copy as extracted from a 2026.5.25 reset package; this project records the current official file as downloaded directly from the official AULA website during initial research. Matching SHA-256 confirms byte identity, not identical provenance. This is a provenance wording conflict, not a structural-data conflict.

### Corrected structural findings — VERIFIED

1. Four known top-level UI project containers:
   - [0x00000000, 0x00A355EC)
   - [0x05B10000, 0x065455EC)
   - [0x065455EC, 0x06F7ABD8)
   - [0x06F7ABD8, 0x079B01C4)

2. The final three UI projects are byte-identical.

3. The final project ends exactly at EOF.

4. The final three projects must not be described as guaranteed recovery copies.

5. Correct page table:
   - start: 0x00021DD0
   - 30 records
   - 12 bytes per record
   - size: 360 bytes / 0x168
   - end: 0x00021F38

6. Correct background descriptor table:
   - start: 0x005C008E
   - 30 records
   - 12 bytes per record
   - size: 360 bytes / 0x168

7. Correct icon descriptor banks:
   - 569 descriptors per bank
   - 12 bytes per descriptor
   - 6,828 bytes / 0x1AAC per bank
   - bank 0: [0x00622A84, 0x00624530)
   - bank 1: [0x00624530, 0x00625FDC)

8. Four standalone user-image structures and the startup animation are structurally verified.

9. Startup animation end:
   - 0x05B0D07C
   - 95,473,788 decimal

### Container coverage — VERIFIED

- container-covered: 70,051,928 bytes / 54.9000%
- container-uncovered: 57,547,116 bytes / 45.1000%
- total: 127,599,044 bytes

This is container coverage, not exact semantic coverage.

"Exact semantic coverage is not currently established." Do not claim that every byte inside a known UI project has understood semantics.

### Zero-filled external gaps — VERIFIED

All six gaps outside the known top-level containers are zero-filled:

1. [0x00A355EC, 0x04000000) — 56,404,500 bytes
2. [0x0404B00B, 0x04060000) — 86,005 bytes
3. [0x040AB00B, 0x040C0000) — 86,005 bytes
4. [0x0410B00B, 0x041E0000) — 872,437 bytes
5. [0x0422B00B, 0x04240000) — 86,005 bytes
6. [0x05B0D07C, 0x05B10000) — 12,164 bytes

"Do not state: 'No unexplained non-padding data exists.'"

### Page 21 verified boundaries

- page record: 0x00021ECC
- display block: [0x00024B7E, 0x00024C4A) — 204 bytes
- touch block: [0x00024C4A, 0x00024DA0) — 342 bytes
- background descriptor table offset: 0x005C018A
- calculation: 0x005C008E + (21 * 12)
- Page 21 referenced icon IDs: 1-9, 13, 14, 20, 21, 119, 318-352

Background descriptor (carefully recorded):
- raw descriptor: 368461004001e00100000010
- address: 0x00618436
- dimensions: 320 x 480
- parsed size: 0
- parsed format: 16

Its exact semantics remain UNVERIFIED and it must not be treated as a normal RGB565, ARGB4444, or LT bitmap descriptor without additional evidence.

The safest currently verified Page 21 offline modification boundary remains equal-size in-place replacement of verified icon payload allocations, including the already documented icon allocations such as IDs 341 and 342.

VERIFIED:
- equal-size in-place replacement can remain inside existing verified payload allocations
- existing Page 21 touch records can remain unchanged
- descriptor-table changes are not required for the verified equal-size workflow
- offline diff confinement can be independently validated

UNVERIFIED:
- image-level self-checksum behavior
- updater acceptance of a modified package
- full updater write scope
- interrupted-write recovery
- hardware safety

### Decode issues

VERIFIED:
- 26 entries fail bitmap bounds validation
- they are unreferenced by known page, display, or touch records
- corresponding entries in the other icon bank are also invalid
- neighboring descriptors do not show table-wide parser desynchronization
- no currently referenced UI asset depends on them

HYPOTHESES:
- reserved slots
- overloaded metadata
- intentionally invalid entries
- non-bitmap records stored in descriptor slots

"No evidence was found that these entries corrupt any currently referenced UI asset. Their intended semantics remain unknown." Do not state that they are definitively not corruption.

### Executable-code assessment

VERIFIED:
- no executable region was identified by the corrected structural analysis
- parsed structures are consistent with resource data
- all gaps outside known top-level containers are zero-filled

UNVERIFIED:
- that every byte in UartTFT-II_Flash.bin is non-executable
- that HFD_Code_V2.2.bin and HFD_Code_V2.3.bin independently contain all screen-MCU executable code

The HFD executable-code attribution currently comes from softce documentation and has not been independently established by this structural report.

### Safety decision

Hardware decision remains NO-GO.

Do not:
- start either firmware updater
- press Start
- flash any BIN
- enter bootloader mode
- replay upgrade traffic
- modify an updater
- assume the official image guarantees recovery
- recommend a hardware write

### Checksum work

Do not recommend rerunning scripts\flash_checksum_scanner.py. The quick/deep checksum investigation is already completed and documented. The image-level self-checksum remains UNKNOWN.

### Next planned task

"Read-only analysis of the native dynamic widget model, focusing on display type 3 variable-to-icon selection and display type 5 animation behavior, to determine whether Page 21 can support Stream Deck-style runtime state feedback without changing touch records or repeatedly writing resource flash."

The analysis should later determine:
- runtime variable addresses used by type 3 widgets
- icon-range selection behavior
- min/max value behavior
- existing pages that demonstrate runtime icon switching
- type 5 start, stop, loop, and frame-selection behavior
- whether Page 21 can reuse an existing volatile RAM variable
- whether Companion feedback can be mapped to native L99 icon states

Do not begin this dynamic-widget task now.

### Companion direction

Future integration direction:
- Bitfocus Companion is the preferred first external platform
- first milestone is input-only integration
- existing Mini Numpad HID events can trigger Companion actions through a local bridge
- initial proof of concept must not require firmware modification or flashing
- bidirectional feedback depends on the dynamic-widget analysis
- OpenDeck remains a later-stage option because it would require a thicker device/rendering adapter

Do not implement Companion or OpenDeck integration in this task.

## External Research Reconciliation and New-Chat Handover

### 1. Current repository state and latest relevant commit

- Repository: C:\temp\aula-l99-controller
- Branch: main
- Remote: miniz3210/aula-l99-controller.git
- Latest commit: 6ed268d "Add firmware-free AULA input bridge prototype"
- Working tree: clean
- Vendor binaries and extracted artifacts are local only and ignored by Git.

### 2. What has been completed

- Factory screen resource image extracted and hash-verified (UartTFT-II_Flash.bin, 127,599,044 bytes, SHA-256 4cb3fa5c...).
- HFD_Code_V2.2.bin (305,800 bytes, SHA-256 432e358c...) and HFD_Code_V2.3.bin (313,652 bytes, SHA-256 a76806ad...) identified and hashed.
- Factory UI parsed: 30 pages, 385 display records, 187 touch records, 1138 icon descriptors, 811 unique decoded images, 3 animations, 134 animation frames.
- Page 21 confirmed as built-in Mini Numpad with 17 touch zones and descriptor range 319–352 mapped.
- Offline descriptor inspector and NumPad icon patcher built (read-only, working-copy only).
- Wired Raw Input attribution for VID 0C45/PID 800A/MI_00.
- make-code-based screen Numpad mapping, Num Lock-independent design.
- Deterministic short/hold state machine.
- Dry-run provider architecture designed.
- Official UI widget crosswalk initiated (icon, GIF, keyboard-key, page, variable concepts).
- Structural analysis of UartTFT-II_Flash.bin completed and independently reviewed.
- Levetop LT168/SDK/UI_Editor-II materials reviewed.
- gavindi/Aula_L99_Linux reviewed.
- kei825/aula-l99-screen-fw reviewed.

### 3. What remains uncommitted, if anything

- Working tree is clean; all completed work is committed.

### 4. Exact evidence categories

A. **User-unit verified** — Directly observed on the user's own AULA L99, official files held by the user, or captures produced from that unit.
B. **AULA vendor artifacts verified** — Derived from official AULA applications, installers, firmware packages, updaters, or official download sources.
C. **Levetop official reference** — Derived from official Levetop documentation, LT168B SDK, LT168B MCU SDK, UI_Editor-II examples, or official compiled reference artifacts.
D. **Public teardown evidence** — Derived from a publicly available AULA L99 teardown/review sample, not from the user's own keyboard.
E. **Third-party research** — Derived from gavindi/Aula_L99_Linux or kei825/aula-l99-screen-fw.
F. **Supported inference** — Strongly suggested by multiple evidence sources but not independently verified.
G. **Unverified** — Not yet proven for the user's exact hardware or firmware revision.

Categories D and E are never presented as direct evidence from the user's own unit.

### 5. User-unit verified facts

- Wired Raw Input attribution: VID 0C45 / PID 800A / MI_00.
- Factory UartTFT-II_Flash.bin size and SHA-256 verified.
- HFD_Code_V2.2.bin and HFD_Code_V2.3.bin sizes and hashes verified.
- Page 21 Mini Numpad: 11 display records, 18 touch records, 17 type 0xC001 action records, descriptor range decimal 319 through 352.
- Descriptor 341/342 mapped; patch feasibility proven for offline working copy only.
- Offline NumPad icon patcher round-trip validated.
- Upload protocol: 154 logical chunks, approximately 309071 bytes, not standard JPEG.

### 6. Levetop official findings

- Official LT168/SDK/UI_Editor-II materials reviewed.
- Official UI widget families identified: icon, GIF, keyboard-key, page, variable.
- Type 3 mapped to official icon widget family.
- Type 5 mapped to official GIF widget family.
- Official example supports at least 90 pages.
- Official runtime model supports widget WriteAddr operations and system page switching through 0x7000.
- Official LT168 memory map, startup/vector model, W25N01GV driver, compiled reference artifacts identified.
- LT168 compatibility strongly supported but must be independently fingerprinted against the user's HFD Code V2.3.
- Earlier generic assumption "widget variable N maps to 0x0600 + N" must not be generalized.

### 7. Public teardown findings (explicitly not from the user's keyboard)

- A public AULA L99 teardown sample shows an HFD168BDP screen controller, HFD80CP100 keyboard MCU, Winbond external memory, and a reported GT911 touch controller.
- The user's own unit has not been physically opened.

### 8. gavindi/Aula_L99_Linux findings and reuse candidates

- Provides substantial reverse engineering of: keyboard HID protocol, RTC/system-monitor packets, screen image/GIF upload, serial transfer behavior, Linux-side tooling.
- Historical LT7689 wording is an engine-lineage or historical hypothesis, not confirmed physical hardware identity; not adopted as confirmed.
- Reuse candidates: HID protocol mapping, telemetry packets, image/GIF upload format, serial transfer behavior.
- Third-party real-hardware claims have not been independently reproduced on the user's unit.

### 9. kei825/aula-l99-screen-fw findings and audit status

- Provides M*Core disassembler/emulator, stock HFD Code V2.2 emulation claims, LT168 MMIO model.
- GT911, W25N01GV, SCI1 and LCD models documented.
- Custom 4x4 deck design and PC-side serial deck implementation documented.
- Detailed hardware/firmware notes provided.
- Repository omits proprietary Levetop engine/SDK components and cannot be treated as a standalone reproducible firmware build.
- No third-party firmware should be flashed without independent compatibility and recovery verification.
- Audit status: reviewed as third-party research; not independently verified on the user's unit.

### 10. Conflicts and corrected assumptions

- LT7689 wording is an engine-lineage or historical hypothesis, not confirmed physical hardware identity.
- HFD168BDP marking comes from a public teardown sample.
- LT168 compatibility is strongly supported but must be independently fingerprinted against the user's HFD Code V2.3.
- Type 3 is now mapped to the official icon widget family.
- Type 5 is now mapped to the official GIF widget family.
- Official UI_Editor-II examples support at least 90 pages.
- Official runtime model supports widget WriteAddr operations and system page switching through 0x7000.
- The earlier generic assumption "widget variable N maps to 0x0600 + N" must not be generalized.

### 11. Current input bridge status

- Firmware-free input bridge POC designed (docs/NATIVE_WIDGET_AND_COMPANION_DESIGN.md).
- Device-aware HID attribution via Raw Input for 0C45:800A.
- Deterministic short/hold state machine (short < 500 ms, dead zone 500–699 ms, hold >= 700 ms).
- Num Lock-independent make-code mapping.
- Bitfocus Companion provider-agnostic architecture.
- Not yet implemented; no source code changes.

### 12. Current dynamic-screen strategy

- Native type 3/type 5 dynamic widget analysis documented (docs/NATIVE_WIDGET_AND_COMPANION_DESIGN.md).
- Type 3 variable-15 record exists on Page 21.
- Type 3 mapped to official icon widget family; type 5 mapped to official GIF widget family.
- "widget variable N maps to 0x0600 + N" assumption must not be generalized.
- Do not begin dynamic-widget task now; next task is HFD Code V2.3 fingerprint.

### 13. Continued hardware NO-GO decision

HARDWARE WRITE STATUS: NO-GO

Unresolved:
- exact user-unit screen-controller revision
- HFD Code V2.3 architecture fingerprint
- modified-resource acceptance
- full updater write scope
- interrupted-write recovery
- independent verification of third-party recovery claims

**Exact next task:**
"Perform a read-only architecture fingerprint of the user's HFD_Code_V2.3.bin against the official Levetop LT168 reference binary, startup/vector model, ISA vocabulary, MMIO constants, and the kei825 M*Core disassembler/emulator assumptions. Do not execute or flash firmware."

**Task after that (do not start):**
"Build a field-level offline crosswalk between official UI_Editor-II icon/GIF/touch records and the AULA resource-image records, then decide whether stock-firmware runtime variables, a resource-only rebuild, or custom firmware is the safest Stream Deck path."

### Agent workflow policy

- Ordinary/free agent: coding, tests, captures, documentation, Companion work, and deterministic analysis.
- REA: only on demand for difficult native executable analysis.
- Normal target: 20k–50k tokens.
- At approximately 60k: stop opening new branches and finish only the current evidence path.
- Hard ceiling: 80k tokens.
- Before 80k: stop and produce a handover.
- Never allow 200k+ exploratory sessions.
