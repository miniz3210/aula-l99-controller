# AULA L99 Project Handover

Continue this project from the verified state below. Do not restart the reverse engineering from scratch and do not repeat tests already marked verified.

## 1. Mission

Turn the AULA L99 keyboard's built-in 320x480 touchscreen into a Stream Deck-style controller: custom icons, multiple independent touch zones, PC-side actions, and dynamic status fields, while preserving the stock touch-to-keyboard logic where practical.

## 2. Current repository state

- Main repository path: C:\temp\aula-l99-controller
- Branch: main
- Remote: miniz3210/aula-l99-controller.git
- Current published release: v0.1.1
- HEAD commit: `0387967` — `docs: record bounded canonical MCore CFG checkpoint`
- Working tree: modified (`scripts/research/hfd_cfg.py`, `tests/test_hfd_cfg_partition.py`); nothing staged, no commits created.
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
- gavindi/Aula_L99_Linux — extensive keyboard and screen protocol research, Linux tools, captures, and upload format work.
- mos9527/evbunpack — Enigma Virtual Box extraction used to inspect the official updater container.

Neither third-party tree is committed to this project, and third-party firmware or artwork is not licensed by this repository.

## 15. Research checkpoints documented (2026-11-14)

**Accepted CFG checkpoints remain unchanged:**
- 4096 baseline (`3ec58fd` implementation, `0387967` documentation)
- Accounting repair (`59696c1cac8c597427374af176fef9e2ab6859bd`)
- 8192/512, 8192/1024, 12288/1024, 12288/1536 (`9c1204152ad56987250b8d9ad1aaec19f1dedcd7`, `PASS_BUDGET_TRUNCATED`)

**Accepted JMPI evidence:**
- Literal-pool helper (`89ca1201ec8ff94497df7d8be68f260b9ff87b58`)
- Standalone post-processor (`8b0b47a51db719721d36bb029de4a4dec7011fd6`)

**Validated JMPI mappings:** 49 out of 52 unresolved indirect-flow sites validated

**ROM jump-table research:** Indirect jump site `0x6004D68A`, ROM table base `0x60016458`, 11 candidate entries (index 0–10), common join `0x6004D742`; all 11 cases write a 32-bit constant to `0x0086EF40`; default path writes `0x0001C200`

## 16. Offline utilities newly accepted with limitations

**Address Xref Scanner:** `ACCEPT_WITH_LIMITATIONS`

**Runtime Frame Codec:** `ACCEPT`

**Capture Frame Classifier:** `ACCEPT_WITH_LIMITATIONS`

**USB Device Attribution Utility:** `ACCEPT_WITH_LIMITATIONS`

**Screen-Control Evidence Inventory:** `ACCEPTED`

**Screen Capture Evidence Utility:** `ACCEPT` (22/22 tests passed; CSV assertion provenance explicit)

**Offline Touch Event Normalizer:** `ACCEPT`

**Offline Action Dispatcher:** `ACCEPT`

## 17. FSM device attribution repair

`ACCEPT_WITH_LIMITATIONS`

## 18. Pending work (not yet accepted or complete)

- Bridge Dispatcher Integration: `ACCEPT` (MockTransport only; real Companion transport NOT IMPLEMENTED)
- Bridge end-to-end device attribution: `NOT YET VERIFIED`
- Real Bitfocus Companion transport: `NOT IMPLEMENTED`
- USB-only visible LCD update: `NOT VERIFIED`

## 19. Firmware identity preservation

**HFD_Code_V2.3.bin:** 313,652 bytes, SHA-256 A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03

## 20. Firmware upgrade distinctions

Keyboard firmware upgrade and screen firmware upgrade are separate paths.

Chinese AULA software 1.0.1.4 remains the research baseline.

## 21. Safety gates preserved

**Firmware flashing:** NO-GO
**Unknown RAM writes:** NO-GO
**CFG budget expansion:** HOLD
**Multi-root expansion:** HOLD
**Type 3 investigation:** HOLD
**GT911 deeper research:** HOLD

## 22. USB evidence limitations

- Capture-local device addresses
- VID/PID descriptor evidence
- CSV mapping assertions
- CRC-valid unsupported opcodes
- 2060-byte uploads are not proof of live framebuffer refresh

## 23. Windows Companion progress

- Raw Input device discovery
- 17-key logical mapping
- Short/hold/secondary-hold FSM
- DryRunProvider
- Offline Touch Event Normalizer
- Offline Action Dispatcher
- Pending Bridge integration

## 24. Current session responsibilities

Session A: Nemotron 3.5 Super VL
Read-only firmware/static audits

Session B: Nemotron 3 Ultra 550B
Architecture and acceptance audits

Session C: Free Coding Agent
Implementation and tests

Session D: Free Coding Agent
Documentation and bounded repairs

## 25. Next planned task

Complete Bridge Dispatcher Integration, independently verify device identity, event ordering, DryRunProvider preservation, and mock dispatch behavior.

Do not mark that task ACCEPTED or COMPLETE until its final report and independent review.

Do not restart firmware discovery.

## 26. Next-chat handover summary

**Research Status:** All accepted checkpoints preserved. CFG and JMPI evidence stable. Offline utilities documented. Safety gates preserved.

**Current status:** Bridge Dispatcher Integration ACCEPTED after independent review. Device propagation verified; real Companion transport NOT IMPLEMENTED.

**Handoff Ready:** Yes - All three allowed documentation files updated, firmware identity preserved, safety constraints maintained.

**Next Steps:** Session D continues documentation and bounded repairs. New chat should continue with Bridge Dispatcher Integration implementation.

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

Uncommitted working-tree changes exist in `scripts/research/hfd_cfg.py` and `tests/test_hfd_cfg_partition.py`. These fix queue accounting (`build_queue_accounting`, `reconcile_queue_accounting`), block-loop exhaustion reporting (`budget_max_basic_blocks` instead of `budget_max_instructions`), the deterministic queue-record schema, candidate-versus-queue metrics, and comparison generation (`generate_comparison_4096_vs_8192`, `--compare-baseline-json`, `--compare-experiment-json`, `--compare-output`). Validation: 99 tests pass, py_compile passes, all six baseline hashes unchanged, experiment runs 1 and 2 deterministic, queue_discovery_record_count = 223, reconciliation 153 + 70 = 223, comparison JSON SHA-256 92D61DD6CF5E9E965965218B9A7BDB9CCA107DDF1D3C20DAE2849FA7AA318310. Do not commit, tag, or push without explicit approval.

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

## 31. Handover — 2026-11-12 — CFG Checkpoint, Ubuntu/Ghidra Verification, 8192 Experiment, Accounting Repair Task

### 31.1 Current repository state

- Branch: main
- HEAD: `59696c1cac8c597427374af176fef9e2ab6859bd` — `fix: reconcile bounded HFD CFG queue accounting` (accounting repair commit)
- Working tree modifications (intentional, pre-existing):
  - `docs/PROJECT_HANDOVER.md`, `README.md`, `CHANGELOG.md` — accounting repair documentation (this task; unstaged)
- Nothing staged.

### 31.2 Completed Ubuntu/Ghidra independent startup verification

An independent verification host (Ubuntu x86_64, OpenJDK 21, Ghidra 12.1.4, REA 6.9.0, ghidra-mcore commit `2f32468f68c3b0eccbc875a26fd0a5769d3bfe91`, language `MCORE:LE:32:default`) was used to verify the startup region of HFD Code V2.3.

- Verified fixture range: `0x60017490` through `0x600174BF` (48 bytes)
- Fixture SHA-256: `F241FCF814F1CC6D654C4AEC270E600A1DF18130ABF87395C0562CFE7DF332DF`
- mcdis listing SHA-256: `9913A3F100B445D51E45FCB1E484179C7B45A506FCF482A5597BBAACE9AE6DC5`
- Ghidra listing: 24 lines, SHA-256 `C24D46A5B6E0DE97E8804C910F6265AC48C3D8A11E916173AA1A80D8F496C9C1`
- Full-startup bounded output SHA-256: `99F028D2857B5F08ECD13DAA82DD175F26AE2D41C004B210E16CE21300404188`

Verified startup observations:
- `0x60017490`: `lrw r1, literal at 0x600174C0`
- `0x600174C0`: `0x00874FFC`
- `0x60017492`: `mov r0, r1`
- `0x60017494`: `lrw r1, literal at 0x600174C4`
- `0x600174C4`: `0x60010000`
- `0x60017496`: `mtcr r1, VBR`
- `0x60017498`: `mfcr r2, VBR`
- `0x6001749A`–`0x600174B6`: register-clearing sequence
- `0x600174B8`: call through literal at `0x600174C8` → `0x60045150` (verified)
- `0x600174BA`: call through literal at `0x600174CC` → `0x600449B0` (verified)
- Verified self-loop: `0x600174BC` → `0x600174BC`

Local Ghidra compatibility patch:
- Installed `mcore_le.cspec` required one local patch: output `pentry maxsize` changed from 1 to 4 for r2.
- Patched `mcore_le.cspec` SHA-256: `296861E645DF2A7FC496EAAD84067C046D7604E27213C6C9B992C0C70E62E8E4`
- This patch allowed Ghidra 12.1.4 to load the compiler specification.
- The patch is NOT vendor-confirmed ABI evidence. ABI correctness remains UNKNOWN.
- Do not treat decompiler argument, return-value, or calling-convention output as verified evidence.

Compiled SLEIGH artifacts:
- `mcore_le.sla`: 8834 bytes, SHA-256 `33F759B82C787135277DB022AFA5662A8A5CBDF19CA3E52896016F76E4B03F84`
- `mcore_be.sla`: 8818 bytes, SHA-256 `5EC072995C10842C15F17E99EA0D1E2CD5271DFD259A188DF964336506C9E31B`

### 31.3 Experimental single-root 8192 safety profile (implementation completed today)

The working copy adds a constrained experimental profile:
- CLI flag: `--experimental-single-root-8192`
- Profile name: `experimental_single_root_8192`
- Required root: `0x60017490` (exactly one)
- Required `max_instructions`: `8192`
- All other budgets remain at `DEFAULT_BUDGETS` defaults (including `max_basic_blocks = 512`)
- Output isolated under `local_analysis/cfg_experiments/`
- `DEFAULT_BUDGETS` unchanged; normal default `max_instructions` remains `4096`
- Profile audited as safe; tests after profile work: 73 passing (before latest accounting repair task)

### 31.4 Genuine 8192 experiment completed today

Command:
```
.venv-analysis\Scripts\python.exe scripts\research\hfd_cfg.py --root 0x60017490 --max_instructions 8192 --experimental-single-root-8192 --output-dir local_analysis\cfg_experiments\single_root_8192
```

Requested and effective `max_instructions`: 8192. All other budgets unchanged.

**Binding budget**: `max_basic_blocks = 512` (hit first, not `max_instructions`).

**Experiment classification originally reported**: `PASS_DIFFERENT_BUDGET_LIMIT` — **Do not present this as fully accepted** because queue and pending accounting in the generated summary was later proven invalid.

**Canonical graph results (structurally usable, deterministic)**:
- Source traversal nodes: 512 (+163 from 4096)
- Source instruction occurrences: 6114 (+2018)
- Source unique instructions: 5238 (+1867)
- Source-node multiply-owned count: 854 (+146), max ownership: 3
- Canonical blocks: 666 (+191)
- Canonical instructions: 5238 (+1867)
- Canonical edges: 869 (+264)
- Unique reachable bytes: 10476 (+3734)
- Accepted functions: 22 (unchanged)
- Unique direct-call candidates: 77 (+11)
- Accepted candidates: 21 (unchanged)
- Queued candidates: 56 (+11)
- Unresolved edges: 32 (+18)
- Outside-observed-map target edges: 154 (+11)
- Return edges: 15 (unchanged)
- Self-loop edges: 1 (unchanged)
- Canonical overlap: 0
- Duplicate canonical instruction ownership: 0
- Duplicate canonical edges: 0
- Prohibited-range access: 0
- Target SHA-256 unchanged
- Two runs produced deterministic graph-output hashes

**New queued candidates observed at 8192** (do not infer purposes):
- `0x600221C0`, `0x600225EC`, `0x600235EC`, `0x60027C7C`, `0x6002F6B0`, `0x6002FCA0`
- `0x60032B28`, `0x60032DD0`, `0x60034B60`, `0x60034D54`, `0x6004C412`

**8192 output hashes from the invalid-accounting run** (identify preserved artifacts; do NOT treat as accepted queue-accounting outputs):
- `cfg_summary.json`: `C2C9634DEACDCA6569DA481ABBA503CE6688976E28916DC7F603A5DFF94552D7`
- `cfg_reproducibility.json`: `0159CE92D9142EFDF0B32374208232B665BC132D4D1D32DBEE797DB13548BDF6`
- `comparison_4096_vs_8192.json`: `743CE281D18AC4222EF06F1F6D14786C5ACCA5DA87E1D0BC81046984EA7AF7F2`

### 31.5 Confirmed queue/pending accounting defects (provenance audit: EXPERIMENT OUTPUT INVALID)

Scope of invalidity: **Queue and pending accounting only.**

**Still usable (deterministic, structurally valid)**:
- `cfg_nodes.json`, `cfg_edges.json`, `cfg_ranges.json`
- Canonical graph metrics and topology
- Structural graph expansion observations
- Target and safety counters
- Deterministic topology evidence

**Not usable (invalid)**:
- `queue_final_status_counts` (hardcoded `{}` in baseline, partially populated but untrusted in 8192)
- `pending_block_work`, `pending_block_count`, `pending_function_work`, `pending_function_count`, `pending_total_work`, `pending_total_count` (hardcoded zeros in baseline)
- `processed_or_resolved_queue_records` (hardcoded 0 in baseline)
- `pending` fields copied into `comparison_4096_vs_8192.json`
- Final experiment acceptance decision based on those fields

**Root causes (confirmed in `scripts/research/hfd_cfg.py`)**:
1. `build_canonical_summary` hardcodes zero/empty values for all queue/pending fields.
2. `queue_discovery_record_count` is real (223 in 8192 experiment, derived from `len(builder.queued_work)`).
3. Raw queue records are not persisted in canonical outputs.
4. Reconciliation skips validation when `queue_final_status_counts` is empty.
5. Block-loop exhaustion records `budget_max_instructions` even when the actual exhausted budget is `max_basic_blocks`.
6. Traversal implementation DID preserve work in `builder.queued_work`.
7. No evidence proves traversal work itself was dropped.
8. Canonical graph topology remains valid.

### 31.6 Current exact next repair task (Windows main development machine, Kilo Code)

**Repair canonical queue and pending accounting.** The repair must:

1. Extract one shared queue-accounting helper from the valid legacy `_build_output` logic.
2. Use the helper in canonical summary, report, preview, and reproducibility output.
3. Persist deterministic `queue_discovery_records`.
4. Replace hardcoded queue and pending zero values.
5. Require fail-loud reconciliation even when status counts are empty.
6. Replace hardcoded `budget_max_instructions` with the actual exhausted budget: `budget_<budget_name>`.
7. Classify all `budget_*` reasons as `pending_budget_exhaustion`.
8. Add tests for `max_instructions`, `max_basic_blocks`, `max_functions`, `max_decoded_bytes`, pending block/function preservation, queue reconciliation, deterministic ordering, and comparison provenance.
9. Add an in-repository deterministic comparison generator with explicit JSON paths and no silent defaults.
10. Rerun the isolated single-root 8192 experiment twice after repair.
11. Keep `max_basic_blocks` at 512.
12. Do not change `DEFAULT_BUDGETS`.
13. Do not add roots.
14. Do not approve a `max_basic_blocks` increase until repaired outputs show the true pending work.

**Only the Windows main machine should perform this repair.** Ubuntu remains an independent Ghidra verification host.

### 31.6a Accounting repair — ACCEPTED

Accounting repair commit: `59696c1cac8c597427374af176fef9e2ab6859bd` — `fix: reconcile bounded HFD CFG queue accounting` (uncommitted working-tree change; do not commit, tag, or push without explicit approval).

Accounting repair:
- Final acceptance: PASS
- Full unittest suite: 262 passing
- CFG partition tests: 99 passing
- Python compilation: PASS
- Baseline artifacts unchanged
- Target SHA-256 unchanged (`A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03`)
- Decoder SHA-256 unchanged (`B6A4B5CBF5E7470AC82A96D19161EC803F3400DC4F65F09B3AECDE74B2A3326A`)
- No prohibited-range access
- No canonical overlaps
- No duplicate canonical ownership or edges

8192 experiment:
- Root: `0x60017490`
- `max_instructions`: 8192
- `max_basic_blocks`: 512
- Binding budget: `max_basic_blocks`
- Acceptance: `PASS_BUDGET_TRUNCATED`
- Canonical blocks: 666
- Canonical instructions: 5238
- Accepted functions: 22
- Candidates: 77
- Queue discoveries: 223
- Processed/resolved: 153
- Pending blocks: 12
- Pending functions: 58
- Pending total: 70
- Reconciliation: 153 + 70 = 223
- Self-loop count: 1
- Prohibited-range access: 0

Reproducibility:
- Two independent fresh-directory runs
- Six matching artifact hashes
- Comparison JSON SHA256: `92D61DD6CF5E9E965965218B9A7BDB9CCA107DDF1D3C20DAE2849FA7AA318310`

### 31.7 Current decision gates

| Gate | Status | Condition |
|------|--------|-----------|
| Accounting repair | ACCEPTED | Final acceptance PASS; 262 unittest tests passing; 99 CFG partition tests passing; py_compile PASS |
| 8192 bounded experiment | ACCEPTED | Binding budget `max_basic_blocks=512`; `PASS_BUDGET_TRUNCATED`; reconciliation 153 + 70 = 223 |
| Commit experimental profile | HOLD | Until repaired accounting and rerun validation |
| Increase `max_basic_blocks` | HOLD | Until repaired outputs show true pending work |
| Change `DEFAULT_BUDGETS` | HOLD | |
| Add vector roots | HOLD | |
| Multi-root expansion | HOLD | |
| Type 3 investigation | HOLD | |
| Ubuntu/Ghidra rerun | Not required | Checkpoint retained |

### 31.8 Evidence classifications to preserve

**VERIFIED**:
- Target identity (size 313652, SHA-256 `A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03`)
- Decoder identity (`mcdis.py` SHA-256 `B6A4B5CBF5E7470AC82A96D19161EC803F3400DC4F65F09B3AECDE74B2A3326A`)
- Root `0x60017490`
- Startup literals (`0x600174C0=0x00874FFC`, `0x600174C4=0x60010000`, `0x600174C8=0x60045150`, `0x600174CC=0x600449B0`)
- Calls to `0x60045150` and `0x600449B0`
- Self-loop `0x600174BC` → `0x600174BC`
- Canonical bounded graph relationships
- Zero prohibited-range access
- Deterministic graph topology

**STRONG STRUCTURAL INFERENCE**:
- Startup initialization role
- `0x00874FFC` as initial stack value
- `0x60010000` as image base and VBR
- Accepted-function entry plausibility
- Little-endian M*Core as working architecture

**STRUCTURAL CANDIDATE**:
- The 56 queued candidates in the 8192 run
- The 11 newly observed queued candidates
- Outside-observed-map valid targets
- Unresolved indirect-flow sites
- Function-purpose hypotheses

**UNKNOWN**:
- Type 3 dispatcher
- Type 3 runtime mapping
- Icon-selection formula
- Transmitter
- ABI correctness of the patched Ghidra compiler spec
- Complete-firmware reachability
- Full vector-root coverage
- True pending-work totals for the current invalid 8192 artifacts

### 31.9 Operational reminders

- 80K-token hard ceiling for context.
- Small bounded-agent-task workflow.
- Documentation, version, commit, stage, tag, and push require explicit user approval.
- The committed 4096 bounded graph (`3ec58fd` implementation, `0387967` documentation) remains the **accepted baseline**.
- The 8192 experiment is recorded as:
  - Structurally informative
  - Deterministic in graph topology
  - Accounting-invalid
  - NOT accepted as a new default candidate

## External Research Reconciliation and New-Chat Handover

### 1. Current repository state and latest relevant commit

- Repository: C:\temp\aula-l99-controller
- Branch: main
- Remote: miniz3210/aula-l99-controller.git
- Latest commit: `0387967` — `docs: record bounded canonical MCore CFG checkpoint`
- Working tree: modified (`scripts/research/hfd_cfg.py`, `tests/test_hfd_cfg_partition.py`); nothing staged, no commits created.
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
- Bounded canonical M*Core CFG tooling added (`scripts/research/hfd_cfg.py`, `tests/test_hfd_cfg_partition.py`).
- Queue-accounting fix and comparison generation added to the CFG tooling (uncommitted).

### 3. What remains uncommitted, if anything

- `scripts/research/hfd_cfg.py` and `tests/test_hfd_cfg_partition.py` are modified in the working tree.
- No commits, tags, or pushes have been created for this work.

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

## Bounded canonical M*Core CFG checkpoint (verified)

### 1. Checkpoint identity

- Tool: `scripts/research/hfd_cfg.py`
- Tests: `tests/test_hfd_cfg_partition.py` (51 standard-library unit tests, all passing)
- Git checkpoint: `3ec58fd` — `research: add bounded canonical MCore CFG tooling`
- Target: `HFD_Code_V2.3.bin`
- Target size: 313652 bytes
- Target SHA-256: `A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03`
- Decoder: `local_analysis/third_party/kei825_aula-l99-screen-fw/emulator/mcdis.py`
- Decoder SHA-256: `B6A4B5CBF5E7470AC82A96D19161EC803F3400DC4F65F09B3AECDE74B2A3326A`
- Candidate image base: `0x60010000`
- Root: `0x60017490`
- Prohibited range: `0x60031198-0x600315D0`
- Current traversal budget: 4096 instructions (max_instructions)
- Roots used: one, `0x60017490`
- Budget increase: not yet performed
- Additional vector roots: not yet added

### 2. Bounded graph result

- bounded_graph_acceptance_status: `PASS_BUDGET_TRUNCATED`
- graph_scope: `bounded_observed_graph`
- graph_fully_canonical: `true`
- output_complete: `false`
- budget exhaustion: `max_instructions`
- source traversal nodes: 349
- source instruction occurrences: 4096
- source unique instructions: 3371
- source-node multiply-owned addresses: 708
- source-node maximum ownership: 3
- canonical blocks: 475
- canonical instructions: 3371
- canonical edges: 605
- canonical overlaps: 0
- duplicate canonical instruction ownership: 0
- duplicate canonical edges: 0
- unique reachable bytes: 6742
- overlap redecoded bytes: 0
- source duplicate occurrence bytes: 1450
- accepted functions: 22
- direct-call candidates: 66 total (21 accepted, 45 queued)
- global max-instructions exhaustion events: 1
- prohibited-range accesses: 0
- tests: 51 passing

### 3. Verified self-loop

- `0x600174BC -> 0x600174BC`
- Exactly one canonical self-loop edge
- The containing canonical block terminates at `0x600174BC`
- No fall-through edge to `0x600174BE`

### 4. Independent Ubuntu/Ghidra verification

Environment:
- REA: 6.9.0 (provider readiness checks only; NOT the primary M*Core disassembly engine)
- Ghidra: 12.1.4
- ghidra-mcore source: https://github.com/CUB3D/ghidra-mcore
- ghidra-mcore commit: `2f32468f68c3b0eccbc875a26fd0a5769d3bfe91`
- Ghidra language: `MCORE:LE:32:default`
- Java: OpenJDK 21
- Host: Ubuntu x86_64

Important limitation:
- REA was used primarily for provider readiness checks.
- The actual independent M*Core verification was performed with Ghidra `analyzeHeadless` and the third-party ghidra-mcore processor.
- Do not overstate REA as the disassembly engine.
- The Ubuntu host should be described as an independent Ghidra M*Core verification host.

ghidra-mcore compatibility detail:
- The source clone remained unchanged and clean.
- The installed little-endian compiler spec required a local compatibility patch for Ghidra 12.1.4:
  output pentry maxsize changed from 1 to 4 for r2.
- Installed patched `mcore_le.cspec` SHA-256:
  `296861E645DF2A7FC496EAAD84067C046D7604E27213C6C9B992C0C70E62E8E4`
- This patch allowed the compiler spec to load.
- The patch must not be described as vendor-confirmed ABI evidence.
- ABI correctness remains UNKNOWN.
- Assembly and bounded control-flow observations may be used as independent structural evidence.
- Decompiler parameter, return-value, and calling-convention conclusions must not be treated as verified.

Compiled SLEIGH artifacts:
- `mcore_le.sla`: size 8834 bytes, SHA-256 `33F759B82C787135277DB022AFA5662A8A5CBDF19CA3E52896016F76E4B03F84`
- `mcore_be.sla`: size 8818 bytes, SHA-256 `5EC072995C10842C15F17E99EA0D1E2CD5271DFD259A188DF964336506C9E31B`

Verified Ubuntu transfer identities:
- `HFD_Code_V2.3.bin`: size 313652, SHA-256 `A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03`
- `mcdis.py`: size 4771, SHA-256 `B6A4B5CBF5E7470AC82A96D19161EC803F3400DC4F65F09B3AECDE74B2A3326A`

Fixture evidence:
- startup fixture: `0x60017490` through `0x600174BF`
- fixture size: 48 bytes
- fixture SHA-256: `F241FCF814F1CC6D654C4AEC270E600A1DF18130ABF87395C0562CFE7DF332DF`
- mcdis listing SHA-256: `9913A3F100B445D51E45FCB1E484179C7B45A506FCF482A5597BBAACE9AE6DC5`
- Ghidra listing: 24 lines
- Ghidra listing SHA-256: `C24D46A5B6E0DE97E8804C910F6265AC48C3D8A11E916173AA1A80D8F496C9C1`
- full-startup bounded listing SHA-256: `99F028D2857B5F08ECD13DAA82DD175F26AE2D41C004B210E16CE21300404188`

Verified full-binary startup observations:
- `0x60017490`: `lrw r1, literal at 0x600174C0`
- literal `0x600174C0`: `0x00874FFC`
- `0x60017492`: `mov r0, r1`
- `0x60017494`: `lrw r1, literal at 0x600174C4`
- literal `0x600174C4`: `0x60010000`
- `0x60017496`: `mtcr r1, VBR`
- `0x60017498`: `mfcr r2, VBR`
- `0x6001749A` through `0x600174B6`: register-clearing sequence
- `0x600174B8`: literal-based call through `0x600174C8`
- literal `0x600174C8`: `0x60045150`
- verified call: `0x600174B8 -> 0x60045150`
- `0x600174BA`: literal-based call through `0x600174CC`
- literal `0x600174CC`: `0x600449B0`
- verified call: `0x600174BA -> 0x600449B0`
- `0x600174BC`: `br 0x600174BC`

### 5. Evidence classification to preserve

VERIFIED:
- Target size and SHA-256
- Decoder SHA-256
- Candidate image-relative mappings used by the bounded analysis
- Root `0x60017490`
- Canonical bounded nodes, ranges, and edges
- Calls:
  - `0x600174B8 -> 0x60045150`
  - `0x600174BA -> 0x600449B0`
- Self-loop: `0x600174BC -> 0x600174BC`
- Zero prohibited-range access
- Deterministic outputs and reproducibility manifest

STRONG STRUCTURAL INFERENCE:
- Startup-like initialization role
- `0x00874FFC` as the initial stack value
- `0x60010000` as image base and VBR value
- Structural plausibility of accepted function entries
- LT168-family little-endian M*Core working architecture

STRUCTURAL CANDIDATE:
- Queued and not-yet-reached direct-call targets
- Outside-observed-map valid targets
- Unresolved indirect-flow sites
- Function-purpose hypotheses unsupported by independent evidence

UNKNOWN:
- Type 3 dispatcher
- Type 3 runtime mapping
- Icon-selection formula
- Transmitter
- Correct ABI semantics of the patched Ghidra compiler spec
- Complete-firmware reachability
- Full coverage of all vector roots
- Purpose of `0x60045150` and `0x600449B0`

### 6. 80K-token hard ceiling and bounded agent-task workflow

- Ordinary/free agent: coding, tests, captures, documentation, Companion work, and deterministic analysis.
- REA: only on demand for difficult native executable analysis.
- Normal target: 20k–50k tokens.
- At approximately 60k: stop opening new branches and finish only the current evidence path.
- Hard ceiling: 80k tokens.
- Before 80k: stop and produce a handover.
- Never allow 200k+ exploratory sessions.

### 7. Chinese 1.0.1.4 baseline and keyboard/screen separation

Chinese version 1.0.1.4 is the analysis baseline because it is currently the only available version known to expose both keyboard firmware upgrade and screen firmware upgrade. These must always be treated as separate upgrade paths targeting different controllers. Do not compare the keyboard updater version and the screen updater version as if they are part of one version sequence.

Keyboard controller firmware and screen-controller firmware are distinct upgrade paths and must never be merged.

### 8. Checksum-scanner requirements

Already documented in section 16 (checksum scanner operation and performance). Quick mode target under 30 seconds, deep-mode cache keyed by source hash/patched hash/scanner version/algorithm list/region map, native CRC implementations, multiprocessing across independent jobs, no full-region rescan for every candidate, mmap/memoryview access, progress reporting, phase timings, deterministic machine-readable output.

### 9. Next task

Create a separate controlled single-root experiment:
- raise only `max_instructions` from 4096 to 8192;
- do not add roots;
- compare the graph incrementally against checkpoint `3ec58fd`;
- stop if prohibited-range, determinism, canonicalisation, or accounting checks fail.

Multi-root expansion remains HOLD.

Documentation, commit, version, tag, and push require explicit user approval.

### 11. Queue-accounting correction and comparison generation (uncommitted)

#### 11.1 Root cause

- `build_canonical_summary` emitted hardcoded empty queue literals instead of real queue accounting.
- `build_canonical_summary` and `validate_graph_consistency` skipped reconciliation when status counts were empty.
- Block-loop exhaustion hardcoded `budget_max_instructions` instead of reporting the actual exhausted budget.
- Queue-accounting logic was duplicated across multiple output paths.

#### 11.2 Implementation changes

1. Added the pure shared helper `build_queue_accounting()`. It returns:

   - `queue_discovery_records`
   - `queue_discovery_record_count`
   - `queue_final_status_counts`
   - `pending_block_work`
   - `pending_block_work_count`
   - `pending_function_work`
   - `pending_function_work_count`
   - `pending_total_work`
   - `pending_total_work_count`
   - `processed_or_resolved_queue_records`
   - `repeated_queue_discovery_count`
   - `queue_reconciliation_status`

   It is used by `_build_output` and `build_canonical_summary`, through
   `_build_queue_summary_from_builder`, and is available to cfg report, reproducibility, and
   preview paths.

2. Added fail-loud queue reconciliation through `reconcile_queue_accounting()`.

   - It enforces all queue-accounting equations.
   - It runs before atomic output replacement.
   - `validate_graph_consistency` no longer skips validation when status counts are empty.

3. Corrected block-loop exhaustion reporting.

   - Exhaustion now uses `reason = f"budget_{be}"`.
   - Example: `budget_max_basic_blocks`.
   - It no longer hardcodes `budget_max_instructions`.
   - Generic `budget_*` reasons and `pending_unprocessed_budget_exhaustion` are classified as
     `pending_budget_exhaustion`.

4. Added a deterministic queue-record schema.

   Each record contains:

   - `target_address`
   - `call_site_address`
   - `depth`
   - `work_type`
   - `reason`
   - `function_id`
   - `final_status`

   Absent values are represented as `null`. Records are deterministically sorted and do not
   use Python tuple formatting.

5. Added candidate-versus-queue metrics:

   - `queued_candidates_scheduled_pending`
   - `queued_candidates_not_scheduled_depth_limit`
   - `queued_candidates_without_function_work_record`

6. Added comparison generation:

   - `generate_comparison_4096_vs_8192()`
   - `--compare-baseline-json`
   - `--compare-experiment-json`
   - `--compare-output`

   Comparison output includes explicit provenance paths and fails loudly when required fields
   are missing. Optional unavailable metrics use `null` together with `value_present: false`
   and a `reason`.

#### 11.3 Validation results

- Tests: **99 passed**, consisting of 73 existing tests and 26 new tests.
- Test framework: `unittest`.
- No firmware execution was performed.
- `py_compile`: passed for both modified Python files.
- All six baseline hashes remained unchanged before and after the implementation.
- Experiment runs 1 and 2 were deterministic across fresh directories.

Queue-accounting results:

- `queue_discovery_record_count = 223`
- Final status counts sum to 223.
- Pending block work: 12
- Pending function work: 58
- Pending total work: 70
- Processed or resolved records: 153
- Reconciliation: `153 + 70 = 223`

Binding-budget result:

- Binding budget: `max_basic_blocks`
- Limit: 512
- Status: `PASS_BUDGET_TRUNCATED`
- Pending block reason: `budget_max_basic_blocks`
- Pending records no longer incorrectly report `max_instructions`

Canonical result:

- Blocks: 666
- Instructions: 5238
- Functions: 22
- Candidates: 77
- Prohibited counters: 0
- Self-loop count: exactly 1
- Target hash remained unchanged, beginning with `A76806AD...`

Comparison JSON SHA-256:

`92D61DD6CF5E9E965965218B9A7BDB9CCA107DDF1D3C20DAE2849FA7AA318310`

#### 11.4 Scope constraints confirmed

- No `DEFAULT_BUDGETS` change.
- No root added.
- No documentation was changed during the implementation phase.
- No commit, tag, push, or version change.
- Experimental output is now valid.

#### 11.5 Remaining recommendation

Add comparison generation to the experiment CI flow so that provenance is regenerated and
validated for every baseline/experiment pair.

### 10. What must not be changed

Do not change Python code, tests, firmware, generated CFG outputs, version files, or analysis budgets.
Do not modify any file other than:
- `docs/PROJECT_HANDOVER.md`
- `README.md`
- `CHANGELOG.md`

Do not:
- claim Type 3 discovery;
- claim full-firmware coverage;
- claim vendor confirmation of M*Core or the Ghidra processor;
- claim the compiler-spec patch is the true ABI;
- change VERSION;
- change code or tests;
- run an 8192 experiment;
- add vector roots;
- commit, tag, or push.

The following documentation updates are in progress and must be preserved:
- `docs/PROJECT_HANDOVER.md` — queue-accounting correction and comparison generation record.
- `README.md` — queue-accounting output schema and comparison CLI.
- `CHANGELOG.md` — corrected, added, and verified entries for the queue-accounting fix.


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

### 14. HFD Code V2.3 Evidence Audit (Completed)

#### 14.1 Verified HFD Code V2.3 Identity
- Target file: `tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin`
- Size: 313,652 bytes
- SHA-256: A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03
- Local analysis artifact only; not added to Git.

#### 14.2 Type 3 Evidence Audit
- Type 3 serialized UI records are 14 bytes.
- Parsed fields: `variable`, `x`, `y`, `first_icon`, `last_icon`, `min_value`, `max_value`.
- Manifest contains multi-state Type 3 records, disproving the earlier claim that all Type 3 records are two-state.
- Universal two-state claim: CONTRADICTED by manifest evidence.

#### 14.3 Architecture Evidence Chain
The working architecture assessment is: **HFD Code V2.3 is little-endian LT168-family M*Core firmware.**
Supporting evidence (STRONGLY SUPPORTED, NOT VENDOR-CONFIRMED):
- Third-party `mcore-elf` build configuration
- M*Core decoder and emulator implementations (`mcdis.py`, `mcemu.py`, `mcemu.c`)
- Little-endian vector and pointer structure
- Flash/image addresses in `0x60000000` space
- SRAM addresses in `0x00800000–0x008BFFFF`
- Minimum 2-byte instruction alignment
- Bounded native decoding with structurally credible branches, calls, returns, stack saves/restores, SRAM/image/MMIO constants, and in-image targets

Do not describe this as Levetop vendor-confirmed.

#### 14.4 Candidate Image Base and Vector Evidence
- Candidate image base: `0x60010000` (STRONG INFERENCE)
- Supported by 21 reproducibly counted non-zero LE32 candidate entries in the first 256 bytes
- Under candidate image base `0x60010000`, all 21 candidate targets are 2-byte aligned and fall within the verified image
- Not independently proven by vendor loader metadata

#### 14.5 M*Core Decoder Validation
- Existing third-party M*Core decoder: `local_analysis/third_party/kei825_aula-l99-screen-fw/emulator/mcdis.py`
- Related emulator semantics: `mcemu.py`, `mcemu.c`
- Python invoked using: `.venv-analysis\Scripts\python.exe` (Python 3.12.10)
- Four bounded candidate regions decoded:
  - 128 bytes from `0x60017490`
  - 64 bytes from `0x6001F958`
  - 64 bytes from `0x6001FA10`
  - 64 bytes from `0x6001F980`
- Across these linear decoding windows:
  - 160 total 16-bit words
  - 152 known mnemonics
  - 8 `.short` fallbacks
  - 95% linear mnemonic coverage
  - 16 direct branch/call targets
  - 16/16 targets 2-byte aligned
  - 16/16 targets within the image
- Semantics agreement for:
  - Load/store immediate scaling
  - BR displacement
  - `loopt`
  - LR/LJ literal addressing
  - `jmp`
  - `jsr`
  - `rts` represented as `jmp r15`

#### 14.6 Linear-Decoding Caveat
The 95% result is linear mnemonic coverage, not proof that 95% of the bytes are reachable executable code.

At candidate entry `0x60017490`, the initial sequence includes:
- Loading candidate stack value `0x00874FFC`
- Loading candidate image/VBR value `0x60010000`
- Control-register setup
- Register initialization
- Calls
- A self-branch at `0x600174BC`

Bytes following that self-branch may include:
- Literal pools
- Embedded data
- Unreachable padding
- Another independent function

Therefore:
- Do not describe all linearly decoded words as reachable code.
- Do not use linear sweep alone to build the next CFG.
- The next phase must use recursive control-flow traversal from defensible entry points.
- Stop traversal at unconditional branches, returns, invalid/fallback words, and established data boundaries.
- Treat call targets and branch targets as candidates requiring validation.

#### 14.7 Claims That Must Remain Unverified or Retracted
Do not state any of the following as verified:
- The Type 3 dispatcher exists at `0x60031198–0x600315D0` → **NOT ESTABLISHED**
- `0x60049D98` is independently verified as the transmitter function → **existing document-supported claim, not independently verified**
- REA was invoked on HFD Code V2.3 → **UNVERIFIED**
- 135,969 instructions were identified → **UNVERIFIED**
- A 32-byte RAM record layout was established → **UNVERIFIED**
- Serialized Type 3 records are copied directly into a 32-byte runtime structure → **UNVERIFIED**
- Type 3 `variable N` maps to RAM word `0x0600 + N` → **UNVERIFIED**
- The icon-selection formula has been established → **UNVERIFIED**
- All Type 3 records are two-state → **CONTRADICTED by manifest evidence**
- ARM/Thumb or SuperH decoding provides evidence for this firmware → **UNVERIFIED**

#### 14.8 Decoder Limitations to Preserve
- `mcdis.py` is a hand-transcribed third-party decoder reportedly derived from binutils M*Core tables.
- The original upstream `mcore-opc.h` and `mcore-dis.c` are not present locally.
- No independent known-good M*Core opcode vectors are available locally.
- Agreement among `mcdis.py`, `mcemu.py`, and `mcemu.c` is not independent validation because they originate from the same third-party repository.
- Duplicate-code/opcode-table first-match ordering remains unverified.
- This limitation was not exercised by the bounded regions used for the GO decision.
- Broader validation may require:
  - Original binutils M*Core opcode tables
  - `mcore-elf-objdump`
  - Or known-good assembler/disassembler vectors

#### 14.9 Current Evidence Classifications

| Claim | Status |
|-------|--------|
| HFD Code V2.3 size and SHA-256 | VERIFIED |
| Type 3 record size (14 bytes) | VERIFIED |
| Type 3 parsed fields | VERIFIED |
| Multi-state Type 3 records exist | VERIFIED |
| Universal two-state Type 3 claim | CONTRADICTED |
| Little-endian M*Core architecture | STRONGLY SUPPORTED, NOT VENDOR-CONFIRMED |
| Candidate image base 0x60010000 | STRONG INFERENCE |
| 21 candidate entries in-range | VERIFIED |
| Bounded decoder validation (4 regions) | VERIFIED |
| 95% linear mnemonic coverage | VERIFIED (linear sweep only) |
| 16 branch/call targets in-image | VERIFIED |
| Semantics agreement with mcemu | VERIFIED (bounded regions) |
| Type 3 dispatcher at 0x60031198–0x600315D0 | NOT ESTABLISHED |
| 0x60049D98 transmitter role | DOCUMENT-SUPPORTED, NOT INDEPENDENTLY VERIFIED |
| Type 3 to runtime RAM mapping | UNVERIFIED |
| Icon-selection formula | UNVERIFIED |
| 32-byte RAM record layout | UNVERIFIED |
| REA invocation on V2.3 | UNVERIFIED |
| 135969 instructions | UNVERIFIED |
| ARM/Thumb/SuperH evidence | UNVERIFIED |

#### 14.10 Current GO/NO-GO State

**GO for bounded M*Core control-flow discovery.**

**NOT GO for claiming that the Type 3 dispatcher, Type 3 runtime mapping, or icon-selection formula has been established.**

#### 14.11 Exact Next Bounded Task

Build a minimal recursive M*Core CFG from the defensible startup/vector entries and their direct call targets, without inspecting the previous Type 3 address claims.

The next task must not begin by decoding `0x60031198–0x600315D0`.

#### 14.12 Prohibited Assumptions
- Do not assume the Type 3 dispatcher location is known.
- Do not assume `0x60049D98` is a verified transmitter.
- Do not assume a 32-byte RAM record layout exists.
- Do not assume serialized Type 3 records map directly to runtime structures.
- Do not assume Type 3 variable N maps to RAM word `0x0600 + N`.
- Do not assume the icon-selection formula is known.
- Do not assume all Type 3 records are two-state.
- Do not assume ARM/Thumb or SuperH decoding is relevant.
- Do not describe linearly decoded words as reachable code.
- Do not use linear sweep alone for CFG construction.
- Do not treat `mcdis.py`/`mcemu.py`/`mcemu.c` agreement as independent validation.
- Do not claim Levetop vendor confirmation for the M*Core architecture assessment.

#### 14.13 80K-Token Hard Ceiling Reminder
- Ordinary/free coding agent for bounded deterministic work.
- REA only on demand for difficult native executable analysis.
- Stop and hand over before 80K tokens.

## 32. HFD CFG 12288/1024 bounded experiment (accepted)

### 32.1 Implementation

- Exact Git commit: `d324b641742b16a18ba8f3c4e1de8f35c575138f` — `research: add bounded 12288-1024 HFD CFG experiment`
- New experimental CLI profile: `--experimental-single-root-12288-blocks-1024`
  - Profile name: `single_root_12288_blocks_1024`
  - Required root: `0x60017490` (exactly one)
  - Required `max_instructions`: `12288`
  - Required `max_basic_blocks`: `1024`
  - All other budgets at `DEFAULT_BUDGETS` defaults
  - Output isolated under `local_analysis/cfg_experiments/single_root_12288_blocks_1024_run1/` and `_run2/`
- `DEFAULT_BUDGETS` unchanged: `max_instructions` remains `4096`, `max_basic_blocks` remains `512`.
- Existing profiles unchanged (`default_bounded`, `single_root_8192`, `single_root_8192_blocks_1024`).

### 32.2 Validation

- Full unittest suite: 295 PASS.
- `py_compile` PASS.
- Two deterministic runs (run1 and run2).
- Six matching artifact hashes (run1 == run2 byte-for-byte for all six standard outputs).
- Queue reconciliation PASS: `253 + 90 = 343`.
- Canonical safety counters zero: `prohibited_range_rejection_count == 0`, `unique_prohibited_target_count == 0`, `canonical_overlap_pair_count == 0`, `canonical_duplicate_instruction_ownership_count == 0`, `overlap_redecoded_byte_count == 0`.
- `budget_exhaustion_status`: `max_basic_blocks` (binding budget).
- `bounded_graph_acceptance_status`: `PASS_BUDGET_TRUNCATED`.

### 32.3 Accepted metrics (12288/1024 vs baseline 8192/1024)

| Metric | 8192/1024 | 12288/1024 | Delta |
|--------|-----------|------------|-------|
| Root | `0x60017490` | `0x60017490` | unchanged |
| `max_instructions` | 8192 | 12288 | +4096 |
| `max_basic_blocks` | 1024 | 1024 | unchanged |
| Binding budget | `max_instructions` | `max_basic_blocks` | changed |
| Canonical blocks | 917 | 1297 | +380 |
| Canonical instructions | 7132 | 10016 | +2884 |
| Canonical edges | 1179 | 1634 | +455 |
| Accepted functions | 48 | 52 | +4 |
| Queue records | 264 | 343 | +79 |
| Pending queue records | 62 | 90 | +28 |
| Unique pending addresses | 59 | 79 | +20 |

Clearly distinguished:
- Queue records: 264 -> 343 (total queue discovery records, including duplicates per call site/depth).
- Deduplicated pending addresses: 59 -> 79 (unique pending block/function work targets).
- Accepted functions: 48 -> 52.

### 32.4 Evidence classifications

VERIFIED:
- Deterministic bounded graph topology (run1 == run2, six matching artifact hashes).
- Queue reconciliation (`253 + 90 = 343`).
- Safety invariants (zero prohibited-range access, zero canonical overlaps, zero duplicate ownership/edges).

UNKNOWN:
- Complete firmware reachability.
- Type 3 dispatcher.
- Type 3 runtime mapping.
- Icon-selection formula.
- Patched Ghidra ABI correctness.

### 32.5 Decision gates

| Gate | Status | Condition |
|------|--------|-----------|
| 12288/1024 bounded experiment | ACCEPTED | `PASS_BUDGET_TRUNCATED`, binding budget `max_basic_blocks=1024`, reconciliation PASS, deterministic runs |
| Change `DEFAULT_BUDGETS` | HOLD | |
| Raise `max_basic_blocks` | HOLD | |
| Add vector roots | HOLD | |
| Multi-root expansion | HOLD | |
| Type 3 investigation | HOLD | |
| Hardware flashing | NO-GO | |

### 32.6 Next research

Read-only frontier analysis of 90 pending queue records representing 79 unique addresses (`analyze_pending.py` preserved untracked).

### 32.7 Source JSON SHA-256 hashes

- Baseline input (`single_root_8192_blocks_1024/cfg_summary.json`): `EF36367B1B71CA7DE2CFC61F3013D85F7EB8569B6BB2EB1A3D5AB6F585AD0BC2`
- Experiment input (`single_root_12288_blocks_1024_run1/cfg_summary.json`): `64B1037BD855392E74E1FEFB40B4C09B1D5432E81355545D40BADAC96E25F14B`

### 32.8 Comparison JSON SHA-256

- `local_analysis/cfg_experiments/comparison_8192_vs_12288.json`: `DFCDD5691CFE0982BF933C9F0558EE3337767514AA160EF6D7C7913AA2C6EC4E`
- Generated via `scripts/research/hfd_cfg.py --compare-baseline-json ... --compare-experiment-json ... --compare-output ...`
- Comparison output does NOT embed source artifact hashes; it records explicit `baseline_json_path` / `experiment_json_path` provenance paths per metric record.

### 32.9 Six reproducibility hashes (run1 == run2)

| Artifact | run1 SHA-256 | run2 SHA-256 | Match |
|----------|--------------|--------------|-------|
| `cfg_summary.json` | `64B1037BD855392E74E1FEFB40B4C09B1D5432E81355545D40BADAC96E25F14B` | `64B1037BD855392E74E1FEFB40B4C09B1D5432E81355545D40BADAC96E25F14B` | yes |
| `cfg_nodes.json` | `B83C5C30A2EC21A0E7C1E35B651E27BD35825C84722935D2B3E3BD4A81B032DB` | `B83C5C30A2EC21A0E7C1E35B651E27BD35825C84722935D2B3E3BD4A81B032DB` | yes |
| `cfg_edges.json` | `EEB2203A8C260F73E1E5C3F8FF3146E09090E7996038246384F4AED6B1F44E0F` | `EEB2203A8C260F73E1E5C3F8FF3146E09090E7996038246384F4AED6B1F44E0F` | yes |
| `cfg_ranges.json` | `3DFFDFA94748D20CDE1ECFED94C97E88FD4DB6CF43C8B2C03B69AC80A82690FE` | `3DFFDFA94748D20CDE1ECFED94C97E88FD4DB6CF43C8B2C03B69AC80A82690FE` | yes |
| `cfg_report.txt` | `729F1E21EF1B306F1C973F28E5BC366FC2BA2F2DB133F55E2A701C6B4B6DB269` | `729F1E21EF1B306F1C973F28E5BC366FC2BA2F2DB133F55E2A701C6B4B6DB269` | yes |
| `cfg_reproducibility.json` | `9F4836F9001CD965E1011D594876167BE9CAF4D5439ABFFC53ED3FBFF89041E6` | `9F4836F9001CD965E1011D594876167BE9CAF4D5439ABFFC53ED3FBFF89041E6` | yes |

### 33. HFD CFG 12288/1536 diagnostic experiment (accepted)

### 33.1 Implementation

- Exact Git commit: `9c1204152ad56987250b8d9ad1aaec19f1dedcd7` — `research: add bounded 12288-1536 HFD CFG diagnostic experiment`.
- New experimental CLI profile: `--experimental-single-root-12288-blocks-1536`
  - Profile name: `single_root_12288_blocks_1536`
  - Required root: `0x60017490` (exactly one)
  - Required `max_instructions`: `12288`
  - Required `max_basic_blocks`: `1536`
  - All other budgets at `DEFAULT_BUDGETS` defaults
  - Output isolated under `local_analysis/cfg_experiments/single_root_12288_blocks_1536_run1/` and `_run2/`
- `DEFAULT_BUDGETS` unchanged: `max_instructions` remains `4096`, `max_basic_blocks` remains `512`.
- Existing profiles unchanged (`default_bounded`, `single_root_8192`, `single_root_8192_blocks_1024`).

### 33.2 Validation

- Full unittest suite: 316 PASS.
- `py_compile` PASS.
- Two deterministic runs (run1 and run2).
- Six matching artifact hashes (run1 == run2 byte-for-byte for all six standard outputs).
- Queue reconciliation PASS: `259 + 89 = 348`; `152 + 107 + 89 = 348`.
- Pending block/function union = 75 unique pending items.
- Canonical safety counters zero: `prohibited_range_rejection_count == 0`, `unique_prohibited_target_count == 0`, `canonical_overlap_pair_count == 0`, `canonical_duplicate_instruction_ownership_count == 0`, `overlap_redecoded_byte_count == 0`.
- `budget_exhaustion_status`: `max_instructions` (binding budget).
- `bounded_graph_acceptance_status`: `PASS_BUDGET_TRUNCATED`.
- Self-loop `0x600174BC` -> `0x600174BC` retained.
- Unresolved canonical indirect-flow edges: 52.

### 33.3 Accepted metrics (12288/1536 vs 12288/1024)

| Metric | 12288/1024 | 12288/1536 | Delta |
|--------|------------|------------|-------|
| Root | `0x60017490` | `0x60017490` | unchanged |
| `max_instructions` | 12288 | 12288 | unchanged |
| `max_basic_blocks` | 1024 | 1536 | +512 |
| Binding budget | `max_basic_blocks` | `max_instructions` | changed |
| Canonical blocks | 1297 | 1330 | +33 |
| Canonical instructions | 10016 | 10223 | +207 |
| Canonical edges | 1634 | 1671 | +37 |
| Accepted functions | 52 | 52 | 0 |
| Reachable bytes | 20446 | 20446 | 0 |
| Queue records | 343 | 348 | +5 |
| Accepted queue records | 152 | 152 | 0 |
| Unresolved queue records | 101 | 107 | +6 |
| Pending queue records | 90 | 89 | -1 |
| Deduplicated pending | 79 | 75 | -4 |

### 33.4 Evidence classifications

VERIFIED:
- Deterministic bounded graph topology (run1 == run2, six matching artifact hashes).
- Queue reconciliation (`259 + 89 = 348`).
- Safety invariants (zero prohibited-range access, zero canonical overlaps, zero duplicate ownership/edges).

UNKNOWN:
- Complete firmware reachability.
- Type 3 dispatcher.
- Type 3 runtime mapping.
- Icon-selection formula.
- Patched Ghidra ABI correctness.

### 33.5 Decision gates

| Gate | Status | Condition |
|------|--------|-----------|
| Accounting repair | ACCEPTED | `PASS`, reconciliation enforcement, budget-exhaustion reporting |
| 8192/512 experiment | ACCEPTED | `PASS_BUDGET_TRUNCATED`, binding budget `max_basic_blocks=512`, reconciliation PASS |
| 8192/1024 experiment | ACCEPTED | `PASS_BUDGET_TRUNCATED`, binding budget `max_basic_blocks=1024`, reconciliation PASS |
| 12288/1024 experiment | ACCEPTED | `PASS_BUDGET_TRUNCATED`, binding budget `max_basic_blocks=1024`, reconciliation PASS |
| 12288/1536 diagnostic experiment | ACCEPTED | `PASS_BUDGET_TRUNCATED`, binding budget `max_instructions`, reconciliation PASS |
| Further budget expansion | HOLD | `max_instructions` now binding; no additional accepted functions |
| Change `DEFAULT_BUDGETS` | HOLD | |
| Add vector roots | HOLD | |
| Multi-root expansion | HOLD | |
| Type 3 investigation | HOLD | |
| Hardware flashing | NO-GO | |

### 33.6 Next research

Read-only static classification of 52 canonical unresolved indirect-flow edges:
- 50 unresolved indirect jumps
- 2 unresolved indirect calls

### 33.7 Source JSON SHA-256 hashes

- Baseline input (`single_root_12288_blocks_1024_run1/cfg_summary.json`): `64B1037BD855392E74E1FEFB40B4C09B1D5432E81355545D40BADAC96E25F14B`
- Experiment input (`single_root_12288_blocks_1536_run1/cfg_summary.json`): `9BBE30E2F10A2FB49A77C76D79E30DB75C872909B1EE637DCA07027CB26AF592`

### 33.8 Comparison JSON SHA-256

- `local_analysis/cfg_experiments/comparison_12288_1024_vs_12288_1536.json`: generated via `scripts/research/hfd_cfg.py --compare-baseline-json ... --compare-experiment-json ... --compare-output ...`
- Comparison output does NOT embed source artifact hashes; it records explicit `baseline_json_path` / `experiment_json_path` provenance paths per metric record.

### 33.9 Six reproducibility hashes (run1 == run2)

| Artifact | run1 SHA-256 | run2 SHA-256 | Match |
|----------|--------------|--------------|-------|
| `cfg_summary.json` | `9BBE30E2F10A2FB49A77C76D79E30DB75C872909B1EE637DCA07027CB26AF592` | `9BBE30E2F10A2FB49A77C76D79E30DB75C872909B1EE637DCA07027CB26AF592` | yes |
| `cfg_nodes.json` | `43D82BED3FFDEF1DDDD56D3E210953D325E00B7320197CA0D268F7B78AE5A4BE` | `43D82BED3FFDEF1DDDD56D3E210953D325E00B7320197CA0D268F7B78AE5A4BE` | yes |
| `cfg_edges.json` | `B8667EE401281634C1F01C7C20CEE5CD13AB2677CBCFA52FCF8A5C8CFAE81838` | `B8667EE401281634C1F01C7C20CEE5CD13AB2677CBCFA52FCF8A5C8CFAE81838` | yes |
| `cfg_ranges.json` | `82B4AC31817B7F899652EC0DF661E315D844BB9F8599C129B5602E30F2236144` | `82B4AC31817B7F899652EC0DF661E315D844BB9F8599C129B5602E30F2236144` | yes |
| `cfg_report.txt` | `6B7D4AD14561502B049DF92CC05B24B705178D779EF93FE7A9E6F270723E7ED5` | `6B7D4AD14561502B049DF92CC05B24B705178D779EF93FE7A9E6F270723E7ED5` | yes |
| `cfg_reproducibility.json` | `36076C84057B21F9A62F2A827A01F99AC0E9F6C4476F58B84563E52BA97DB8B9` | `36076C84057B21F9A62F2A827A01F99AC0E9F6C4476F58B84563E52BA97DB8B9` | yes |

### 34. JMPI evidence research checkpoint (accepted, documentation sync)

**Repository state at checkpoint:** HEAD `8b0b47a51db719721d36bb029de4a4dec7011fd6` (`main...origin/main [ahead 2]`), tracked working tree clean, `analyze_pending.py` untracked. No source/firmware changes in this documentation sync.

#### 34.1 Accepted implementation (verified)

| Component | Commit | Subject | Files |
|-----------|--------|---------|-------|
| Literal-pool helper | `89ca1201ec8ff94497df7d8be68f260b9ff87b58` | `research: add validated MCore literal pool helper` | `scripts/research/mcore_literal_pool.py`, `tests/test_mcore_literal_pool.py` |
| Standalone post-processor | `8b0b47a51db719721d36bb029de4a4dec7011fd6` | `research: add deterministic JMPI evidence postprocessor` | `scripts/research/jmpi_evidence_postprocess.py`, `tests/test_jmpi_evidence_postprocess.py` |

- Standalone post-processor is independent of CFG traversal (reads accepted CFG artifacts/manifest; no CFG traversal integration).
- `DEFAULT_BUDGETS` unchanged; no roots added.
- Existing accepted CFG artifacts unchanged.

#### 34.2 JMPI literal-pool evidence (artifact-derived, verified)

- Artifact: `local_analysis/cfg_experiments/jmpi_evidence_postprocess/jmpi_literal_pool_evidence.json`
- Deterministic evidence SHA-256 (verified): `B4D4D323E8B948F1D87D6DB008A016049B6C2D728CA78B595A2D14DC903C1AA3`
- 52 unresolved indirect-flow sites (record-level total).
- 49 validated JMPI literal targets (record-level).
- 3 register-indirect sites preserved (record-level).
- 15 unique literal targets.
- 0 invalid literal targets.
- Deterministic post-processor output.
- Canonical membership for validated JMPI literal-target records (49 records): 23 `BLOCK_START`, 1 `INSIDE_BLOCK`, 25 `NON_CANONICAL`. (Artifact-wide membership includes 3 preserved register-indirect records classified `NON_CANONICAL`; record-level and unique-target counts are distinguished.)

#### 34.3 ROM jump-table research (recorded static findings)

- Indirect jump site: `0x6004D68A`
- ROM table base: `0x60016458`
- 11 candidate entries, index 0 through 10.
- Common join: `0x6004D742`
- All 11 cases write a 32-bit constant to `0x0086EF40`.
- Default path writes `0x0001C200`.
- ISA semantics remain decoder-dependent.
- `0x0086EF40` cross-reference audit remains incomplete due to agent output-limit interruption.
- Do not claim hardware register purpose for `0x0086EF40`.

#### 34.4 Cleanup

- Legacy traversal-integrated JMPI implementation: RETIRED.
- Backup patch: `C:\temp\aula-l99-jmpi-legacy-backup.patch`
- Backup SHA-256 (verified): `01CA8DD905211502A77FC4620B1BDEF411253AFB9FDB6E01E31F427BB08F659F`
- Accepted CFG profiles remain unchanged.
- `analyze_pending.py` remains untracked.

#### 34.5 Decision gates

| Gate | Status |
|------|--------|
| Literal-pool helper | ACCEPTED |
| Standalone post-processor | ACCEPTED |
| Legacy integrated JMPI mode | RETIRED |
| CFG budget expansion | HOLD |
| Resolved-edge integration | HOLD |
| Type 3 investigation | HOLD |
| Hardware flashing | NO-GO |

#### 34.6 Next research

- Bounded `0x0086EF40` cross-reference audit.
- Screen-control protocol research.
- Independent ISA verification when needed.

#### 34.7 Validation

- `python -m pytest tests -q`: 356 passed in 12.74s (repo `tests/` suite). Full-root `pytest -q` reports external `tools/Aula_L99_Linux-main/...` collection issues outside this repository's test scope.
- Documentation sync modified only: `README.md`, `CHANGELOG.md`, `docs/PROJECT_HANDOVER.md`.

### 35. Offline research checkpoints documentation sync (accepted)

**Repository state at sync:** HEAD `13b1ff06d99c837a1c2690ae897f84d27a51db66` (`main`, up to date with `origin/main`). Tracked working tree clean. Staged new files: `docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md`, `scripts/research/hfd_address_xrefs.py`, `scripts/research/l99_runtime_frame_codec.py`, `scripts/research/l99_capture_frame_classifier.py`, `scripts/research/l99_usb_device_attribution.py`, `tests/test_hfd_address_xrefs.py`, `tests/test_l99_runtime_frame_codec.py`, `tests/test_l99_capture_frame_classifier.py`, `tests/test_l99_usb_device_attribution.py`. Untracked: analysis scripts and outputs.

#### 35.1 Accepted checkpoints

| # | Component | Path | Acceptance | Key Limitation |
|---|-----------|------|------------|----------------|
| 1 | Address Xref Scanner | `scripts/research/hfd_address_xrefs.py`, `tests/test_hfd_address_xrefs.py` | ACCEPT_WITH_LIMITATIONS | Raw byte-pattern scan only; instruction references require full CFG validation not performed |
| 2 | Offline Runtime Frame Codec | `scripts/research/l99_runtime_frame_codec.py`, `tests/test_l99_runtime_frame_codec.py` | ACCEPT | Third-party Levetop protocol reference; **UNVERIFIED on user unit** — no live capture |
| 3 | Capture Frame Classifier | `scripts/research/l99_capture_frame_classifier.py`, `tests/test_l99_capture_frame_classifier.py` | ACCEPT_WITH_LIMITATIONS | Operates on existing CSV captures only; device addresses capture-local, not generalizable |
| 4 | USB Device Attribution Utility | `scripts/research/l99_usb_device_attribution.py`, `tests/test_l99_usb_device_attribution.py` | ACCEPT_WITH_LIMITATIONS | Requires tshark; capture-local addresses only; no live USB access; output capture-specific |
| 5 | Screen-Control Evidence Inventory | `docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md` | ACCEPTED | Documentation sync only |

#### 35.2 Review pending

| Component | Path | Status |
|-----------|------|--------|
| Screen Capture Evidence Utility | `scripts/research/l99_screen_capture_evidence.py`, `tests/test_l99_screen_capture_evidence.py` | ACCEPT — 22/22 tests passed; CSV assertions are not descriptor verification |

#### 35.3 Tool descriptions and paths

**Address Xref Scanner** (`scripts/research/hfd_address_xrefs.py`)
- Bounded deterministic offline scanner for references to target address `0x0086EF40` in `HFD_Code_V2.3.bin`
- Raw byte-pattern scan for LE32 `40 EF 86 00` + bounded local instruction-context inspection (immediate 2-byte word)
- Classifies instruction kind: `jmpi` (0x70xx), `jsri` (0x7Fxx), `other`, `unaligned`, `truncated`
- Flags prohibited range `0x60031198-0x600315D0`
- Verifies firmware: size 313652, SHA-256 `A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03`
- Image base: `0x60010000`, image end: `0x6005C934`
- Usage: `python scripts/research/hfd_address_xrefs.py`

**Offline Runtime Frame Codec** (`scripts/research/l99_runtime_frame_codec.py`)
- Deterministic offline encoder/decoder for AULA L99 short runtime USB protocol
- Frame format: `5A A5 | length:u8 | body | CRC16:LE16`, length = len(body) + 2
- Read opcode: `0x03 | word_address:BE16 | word_count:BE16` (max 8 words)
- Write opcode: `0x10 | word_address:BE16 | word_0:BE16 | word_1:BE16 ...`
- Address range: 0x0000–0xFFFF (16-bit word indices)
- CRC16/MODBUS: reflected polynomial 0xA001, init 0xFFFF
- Includes `encode_read_frame`, `encode_write_frame`, `decode_frame`, `decode_read_body`, `decode_write_body`, round-trip tests
- No hardware access, no external dependencies
- Usage: `python scripts/research/l99_runtime_frame_codec.py` (runs offline tests)

**Capture Frame Classifier** (`scripts/research/l99_capture_frame_classifier.py`)
- Deterministic offline classifier for existing USB capture CSV exports
- Frame classes: `VALID_RUNTIME`, `INVALID_RUNTIME`, `UNVERIFIED_LARGE_PAYLOAD`, `UNKNOWN`, `CRC_VALID_UNSUPPORTED_OPCODE`
- Endpoint attribution via capture-local device mapping (`get_endpoint_attribution`)
- Known capture: `aula_home_numpad_transition` with device mapping:
  - Device 6: 05E3:0626 (Genesys Logic USB Hub)
  - Device 13: 1A86:8091 (Touch/pointer)
  - Device 15: EEEF:268A (Screen CDC) — **VERIFIED_SCREEN**
  - Device 16: 0C45:800A (Keyboard HID) — **VERIFIED_NON_SCREEN**
- Bounded memory, no hardware access
- Usage: `python scripts/research/l99_capture_frame_classifier.py` (expects `capture_analysis/` directory)

**USB Device Attribution Utility** (`scripts/research/l99_usb_device_attribution.py`)
- Extracts capture-local USB device address → VID/PID from pcapng via tshark
- Verifies capture SHA-256 before processing: `B4DAD6E13612C615F3A03400BCC9EED8F98F6D02E0B256368B8E82C3C608F5EE`
- Targets device addresses: 6, 13, 15, 16
- Preserves capture-local device addresses; does NOT generalize across captures
- Requires tshark (default `C:\Program Files\Wireshark\tshark.exe`)
- Default capture: `C:\temp\aula-l99-controller\aula_home_numpad_transition.pcapng`
- Usage: `python scripts/research/l99_usb_device_attribution.py` (or with `--capture` and `--expected-sha256`)

**Screen-Control Evidence Inventory** (`docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md`)
- Consolidated inventory of USB-only screen-control evidence from accepted checkpoints
- Sections: Verified USB interfaces, Image upload behavior, Runtime RAM protocol, Touch transport, Display-update limitations, Page-switch status, GT911 status, LT168/LT268 uncertainty, Hardware restrictions, Open questions, Next milestone evidence recommendations

#### 35.4 USB capture-local mapping rules

- USB device addresses (e.g., Device 6, 13, 15, 16) are **capture-local** and must NOT be generalized across different captures.
- The `aula_home_numpad_transition.pcapng` mapping is specific to that capture file (SHA-256 `B4DAD6E13612C615F3A03400BCC9EED8F98F6D02E0B256368B8E82C3C608F5EE`).
- Device 15 (EEEF:268A) is VERIFIED_SCREEN; Device 16 (0C45:800A) is VERIFIED_NON_SCREEN for this capture only.
- Device 6 (05E3:0626) and Device 13 (1A86:8091) are attributed as **VERIFIED_NON_SCREEN** endpoints for this capture only.
- Any new capture requires fresh tshark extraction and verification; do not assume device addresses persist.

#### 35.5 Known SHA-256 evidence (from accepted checkpoints)

| Artifact | SHA-256 | Context |
|----------|---------|---------|
| `HFD_Code_V2.3.bin` | `A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03` | Verified firmware (313652 bytes) |
| `aula_home_numpad_transition.pcapng` | `B4DAD6E13612C615F3A03400BCC9EED8F98F6D02E0B256368B8E82C3C608F5EE` | USB capture for device attribution |
| `jmpi_literal_pool_evidence.json` | `B4D4D323E8B948F1D87D6DB008A016049B6C2D728CA78B595A2D14DC903C1AA3` | JMPI evidence artifact |
| `comparison_4096_vs_8192.json` (repaired) | `92D61DD6CF5E9E965965218B9A7BDB9CCA107DDF1D3C20DAE2849FA7AA318310` | CFG comparison |
| `comparison_8192_vs_12288.json` | `DFCDD5691CFE0982BF933C9F0558EE3337767514AA160EF6D7C7913AA2C6EC4E` | CFG comparison |
| `cfg_summary.json` (12288/1536 run1) | `9BBE30E2F10A2FB49A77C76D79E30DB75C872909B1EE637DCA07027CB26AF592` | CFG experiment |
| `cfg_reproducibility.json` (12288/1536) | `36076C84057B21F9A62F2A827A01F99AC0E9F6C4476F58B84563E52BA97DB8B9` | CFG reproducibility |
| JMPI legacy backup patch | `01CA8DD905211502A77FC4620B1BDEF411253AFB9FDB6E01E31F427BB08F659F` | Legacy JMPI implementation backup |

#### 35.6 Current session workflow

1. **Documentation sync only** — no source code, firmware, or test modifications
2. Record current HEAD (`13b1ff06d99c837a1c2690ae897f84d27a51db66`) and Git status before editing
3. Inspect existing documentation (README.md, CHANGELOG.md, PROJECT_HANDOVER.md)
4. Add concise tool descriptions to README.md
5. Add Unreleased CHANGELOG entry for five accepted checkpoints
6. Update PROJECT_HANDOVER.md with:
   - Tool paths and acceptance status
   - Important limitations per checkpoint
   - USB capture-local mapping rules
   - Known SHA-256 evidence table
   - Current session workflow
   - Next USB-only display-control milestone
7. Preserve all verified firmware identity, CFG/JMPI checkpoints, hardware NO-GO, runtime LCD UNKNOWN, GT911 HOLD
8. Do NOT claim opcode 0x64 is verified screen-control command
9. Do NOT claim 2060-byte packets prove live framebuffer refresh
10. Do NOT alter existing research tools
11. Do NOT stage/unstage files, commit, tag, push, or version bump
12. Validate: `git diff --check`, confirm only three allowed files changed, record SHA-256 before/after

#### 35.7 Next USB-only display-control milestone

**Milestone gate:** USB-only screen control requires **P1** evidence:
- Live capture of short runtime frames (5A A5) during native widget interaction via USB capture (USBPcap) + screen recording while using official AULA software
- Verify Type 3 variable addresses & icon-selection formula via HFD Code V2.3 disassembly (bounded CFG) + live RAM read via short runtime protocol

**Repository artifacts to produce:**
- `screen_runtime_capture.pcapng`, `runtime_frame_log.json`
- `type3_dispatcher_analysis.md`, `variable_address_map.json`

**P2 evidence (parallel track):**
- Official L99 ISP V1.23.exe update capture (Procmon + USBPcap per `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md`)
- Image-level self-checksum resolution (`scripts/flash_checksum_scanner.py --mode deep` + HFD Code checksum handler analysis)
- Win32 overlapped I/O uploader for 2060-byte packets (`scripts/replay_captured_screen_win32.py`)

**Critical blockers for GO decision (unchanged):**
1. Image-level self-checksum in `UartTFT-II_Flash.bin` (UNKNOWN)
2. Exact UI-only package acceptance by updater (STRONG_INFERENCE only)
3. Interrupted-write recovery behavior (UNKNOWN)
4. Live RAM write → visible LCD update path (UNVERIFIED on user unit)

### External Research Reconciliation and New-Chat Handover

**Repository state at checkpoint:** HEAD `8b0b47a51db719721d36bb029de4a4dec7011fd6` (`main...origin/main [ahead 2]`), tracked working tree clean, `analyze_pending.py` untracked. No source/firmware changes in this documentation sync.

#### 34.1 Accepted implementation (verified)

| Component | Commit | Subject | Files |
|-----------|--------|---------|-------|
| Literal-pool helper | `89ca1201ec8ff94497df7d8be68f260b9ff87b58` | `research: add validated MCore literal pool helper` | `scripts/research/mcore_literal_pool.py`, `tests/test_mcore_literal_pool.py` |
| Standalone post-processor | `8b0b47a51db719721d36bb029de4a4dec7011fd6` | `research: add deterministic JMPI evidence postprocessor` | `scripts/research/jmpi_evidence_postprocess.py`, `tests/test_jmpi_evidence_postprocess.py` |

- Standalone post-processor is independent of CFG traversal (reads accepted CFG artifacts/manifest; no CFG traversal integration).
- `DEFAULT_BUDGETS` unchanged; no roots added.
- Existing accepted CFG artifacts unchanged.

#### 34.2 JMPI literal-pool evidence (artifact-derived, verified)

- Artifact: `local_analysis/cfg_experiments/jmpi_evidence_postprocess/jmpi_literal_pool_evidence.json`
- Deterministic evidence SHA-256 (verified): `B4D4D323E8B948F1D87D6DB008A016049B6C2D728CA78B595A2D14DC903C1AA3`
- 52 unresolved indirect-flow sites (record-level total).
- 49 validated JMPI literal targets (record-level).
- 3 register-indirect sites preserved (record-level).
- 15 unique literal targets.
- 0 invalid literal targets.
- Deterministic post-processor output.
- Canonical membership for validated JMPI literal-target records (49 records): 23 `BLOCK_START`, 1 `INSIDE_BLOCK`, 25 `NON_CANONICAL`. (Artifact-wide membership includes 3 preserved register-indirect records classified `NON_CANONICAL`; record-level and unique-target counts are distinguished.)

#### 34.3 ROM jump-table research (recorded static findings)

- Indirect jump site: `0x6004D68A`
- ROM table base: `0x60016458`
- 11 candidate entries, index 0 through 10.
- Common join: `0x6004D742`
- All 11 cases write a 32-bit constant to `0x0086EF40`.
- Default path writes `0x0001C200`.
- ISA semantics remain decoder-dependent.
- `0x0086EF40` cross-reference audit remains incomplete due to agent output-limit interruption.
- Do not claim hardware register purpose for `0x0086EF40`.

#### 34.4 Cleanup

- Legacy traversal-integrated JMPI implementation: RETIRED.
- Backup patch: `C:\temp\aula-l99-jmpi-legacy-backup.patch`
- Backup SHA-256 (verified): `01CA8DD905211502A77FC4620B1BDEF411253AFB9FDB6E01E31F427BB08F659F`
- Accepted CFG profiles remain unchanged.
- `analyze_pending.py` remains untracked.

#### 34.5 Decision gates

| Gate | Status |
|------|--------|
| Literal-pool helper | ACCEPTED |
| Standalone post-processor | ACCEPTED |
| Legacy integrated JMPI mode | RETIRED |
| CFG budget expansion | HOLD |
| Resolved-edge integration | HOLD |
| Type 3 investigation | HOLD |
| Hardware flashing | NO-GO |

#### 34.6 Next research

- Bounded `0x0086EF40` cross-reference audit.
- Screen-control protocol research.
- Independent ISA verification when needed.

#### 34.7 Validation

- `python -m pytest tests -q`: 356 passed in 12.74s (repo `tests/` suite). Full-root `pytest -q` reports external `tools/Aula_L99_Linux-main/...` collection issues outside this repository’s test scope.
- Documentation sync modified only: `README.md`, `CHANGELOG.md`, `docs/PROJECT_HANDOVER.md`.

## External Research Reconciliation and New-Chat Handover
