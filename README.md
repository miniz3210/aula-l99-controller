

### Current product direction (2026-11-24 checkpoint)

The target is a **real Stream Deck-style AULA L99**, not a numpad key remapper: a Windows visual editor defines icons, button geometry, actions, profiles, and feedback; the L99 displays custom UI/NAND resources and returns device-specific touch events; Windows updates state/variables and integrates with Companion, Macro Deck, or another open-source macro engine.

**Preferred development architecture:** stock screen MCU firmware + custom UI/NAND + dedicated bidirectional Windows bridge. A replacement MCU firmware is a fallback, not the default. The official screen flash workflow has worked, but custom image deployment and recovery remain gated.

**Verified offline:** 30-page factory UI structure (385 widget, 187 touch records); Page 21 Mini Numpad 17/17 touch-to-UART events; Page 22 Calculator rendering `12+3=15`; reproducible factory-image header CRC rule. **Unresolved:** complete mutable UI serializer/relocation, host Type 1/Type 3 variable semantics, dedicated touch transport, independent recovery, safe custom image acceptance, production-ready editor/bridge. Reproducing a CRC is not proof that a modified image is accepted or recoverable.

**S1-S5 checkpoint:** S1/S2 structural research partially accepted; S3 variable command not established; S4 HID bridge evidence accepted with limitations; S5 page ranking rejected because it confused Page 21 (Mini Numpad) with Page 22 (Calculator), mislabeled Play, and used stale evidence. Page 19 (Real-time Data), Page 20 (Play), and low-record pages are candidates for bounded investigation, not approved modification targets.

**OpenDeck live integration (2026-11-23 checkpoint):** PASS_VERIFIED_LIVE_WINDOWS for OD1-R2 (AULA L99 4x4 virtual device registered; Rust Named Pipe IPC works; touch 0x50 triggered a real OpenDeck action; Google Open URL action executed) and OD1-R3-H1 (genuine OpenDeck setImage callbacks received; JPEG source identified; JPEG decoded and normalized to PNG; callback count increased 3 to 8; normalized PNG SHA-256 changed after icon change; Rust release build passed; existing touch IPC preserved). OD2-B-R2 PASS_VERIFIED_LIVE_WINDOWS_TO_MOCK (genuine Rust callback events; local callback spool verified; Python CallbackSpoolConsumer processed 30 CLEAR_POSITION and 2 SET_IMAGE events; PNG converted to RGB565 little-endian, 19,200 bytes per 80x120 image; RGB565 SHA-256 4054fd8bf8d20d967ac923cd940056a4e90e2b096ea93e54cbea6d4acafedef4; MockTransport received one image update; duplicate suppression worked). MockTransport PASS does NOT mean physical L99 screen output is verified.

**Pending OpenDeck tasks:** OD2-A-R1 Real Named Pipe Input Adapter integration; HW2 physical touchscreen transport testing; physical L99 icon/framebuffer delivery unverified. DI-D1: 21/21 offline tests PASS; live integration pending. Physical dynamic icon output unverified. Physical touchscreen input unverified. Original physical Numpad functionality must be preserved.

**Native runtime instrumentation (2026-11-24 checkpoint):** DI-TRACE-NATIVE PASS_NATIVE_EVENT_CAPTURE. Process-isolated CEmu execution on HFD_Code_V2.2.bin (305800 bytes, SHA-256 432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf). Page 1 and Page 21 opened. 128173 sampled instruction events. Event counts: 30 UART RX, 356 LCD command, 2100 sampled LCD pixel writes, 20 UART TX, 81798 NAND events. Both child processes exited successfully. No physical hardware writes. Evidence limitations: sampled events do not prove complete instruction coverage. UART RX and LCD writer PCs recorded but complete UART command → renderer → LCD dataflow not established.

**MCORE research preserved:** HFD V2.2/V2.3 firmware identities, MCore Ghidra native analysis, function maps, High P-code evidence, instruction-level call graph, MCORE-CALL-GATE, MCORE-LIFT-FIX, DI-DATAFLOW-CLOSURE, DI-R2 bounded SSA analysis, DI-NATIVE-CLOSURE. Semantic closure not claimed.

**Next workstreams:** (1) UI/NAND builder and emulator-only custom layout validation, (2) dedicated L99 touch transport, (3) variable-driven icon/text feedback, (4) Windows editor/macro integration, (5) controlled UI-only deployment/recovery validation, (6) OD2-A-R1 Named Pipe Input Adapter integration, (7) HW2 physical touchscreen transport testing, (8) DI-TRACE-CORRELATE — correlate native runtime event PCs with MCore function boundaries. Physical custom firmware/UI flashing remains NO-GO pending an explicit evidence-gated decision.

Research outputs suitable for version control belong under `u76/s1`, `u76/s2`, etc., in this repository; vendor binaries, large captures, temporary emulator images, and Ghidra caches stay local/ignored. See the latest checkpoint in `docs/PROJECT_HANDOVER.md`.
# AULA L99 Touchscreen Reverse Engineering and Stream Deck Bridge

Windows-oriented research and tooling for turning the AULA L99 keyboard touchscreen into a Stream Deck-style controller.

## Project status

This is an active reverse-engineering and prototyping project. The present milestone is:

### Primary objective

Turn the wired AULA L99 320x480 screen into a Stream Deck-like programmable controller.

### Preferred architecture under investigation

Stock screen firmware +
Custom UI/NAND resources +
Host-side input/output bridge +
Macro Deck or Bitfocus Companion

This architecture is NOT yet fully implemented.

### Current capabilities

VERIFIED STATIC:
- 30-page UI structure.
- Widget/touch record boundaries.
- RAM-relocated programming routine.
- Page 21 touch rectangles and event identifiers.

VERIFIED OFFLINE:
- Page 21 17/17 button event mapping.
- UART body 41 FF FF 00 XX.
- Page 21 to Page 1 navigation.

VERIFIED LIVE (OpenDeck, 2026-11-23):
- OD1-R2: AULA L99 4x4 virtual device registered; Rust Named Pipe IPC works; touch 0x50 triggered a real OpenDeck action; Google Open URL action executed.
- OD1-R3-H1: Genuine OpenDeck setImage callbacks received; JPEG source identified; JPEG decoded and normalized to PNG; callback count increased 3 to 8; normalized PNG SHA-256 changed after icon change; Rust release build passed; existing touch IPC preserved.
- OD2-B-R2: Genuine Rust callback events; local callback spool verified; Python CallbackSpoolConsumer processed 30 CLEAR_POSITION and 2 SET_IMAGE events; PNG converted to RGB565 little-endian, 19,200 bytes per 80x120 image; RGB565 SHA-256 4054fd8bf8d20d967ac923cd940056a4e90e2b096ea93e54cbea6d4acafedef4; MockTransport received one image update; duplicate suppression worked. MockTransport PASS does NOT mean physical L99 screen output is verified.

UNRESOLVED:
- Physical USB touch-to-host transport.
- Complete reportToHost protocol.
- Widget/resource/variable semantics.
- Full UI image serializer.
- Image checksum coverage.
- Adding a 31st page.
- Macro Deck integration.
- Independent bootloader recovery.

### Safety decision

Offline UI research: GO.
Emulator-only UI mutation: HOLD.
Custom firmware flashing: NO-GO.

Do not claim a working physical Stream Deck controller.

## Screen research summary (2026-11-20)

- Open-source screen-firmware direction identified: https://github.com/kei825/aula-l99-screen-fw (M*Core disassembler/emulator, LT168 MMIO model; omits proprietary Levetop engine/SDK components; not a standalone reproducible firmware build; no third-party firmware should be flashed without independent verification).
- Chinese AULA software version 1.0.1.4 confirmed as the only verified baseline exposing both keyboard and screen firmware upgrade as separate paths targeting different controllers.
- Keyboard (USB HID VID 0C45/PID 800A) and screen (CDC VID EEEF/PID 268A) firmware paths remain explicitly separate; no cross-controller write path verified as safe.
- Official screen updater L99_ISP_CNUI_V1.23_156.exe successfully launched with Fn+X+0+6 to enter screen update mode (bootloader COM4); evidence only — no custom firmware flashed.
- DeviceDriver.exe/HardwareMonitor telemetry writes to C:\Program Files (x86)\AULA L99\data.ini (CPU_Temperature/GPU_Temperature).
- LT168B NOT confirmed hardware; teardown photos show HFD168BDP screen controller marking; relation to Levetop LT168B is inference.
- Screen sub-board SI-2686-TFT-3.98 V01; flash Winbond 25N01GV; touch IC Goodix GT911; SW2 push switch; four test pads (probably PGMCK/PGMIO/RST, not verified by continuity).
- Hardware flashing: NO-GO. SAFE_FLASH_NOT_READY. Preserve official path; do not flash speculative/custom image; establish image layout/checksums/target memory regions/page counts/updater validation/recovery boundaries first.
- Overnight REA package being prepared/executed separately; output not yet reviewed. Do not claim conclusions until reviewed.
- Next task: Review overnight REA output, map conclusions to reproducible evidence, decide if evidence sufficient for non-flashing screen-runtime prototype; do not proceed to custom flashing solely from inferred image structure.
- Detailed 2026-11-20 entries (E52-E54, cap4/cap5, LT168 manual pages, UI format findings, teardown photos) appear in CHANGELOG.md.

## Transport separation and custom firmware direction

Keyboard events (USB HID VID 0C45/PID 800A) and screen runtime updates (CDC VID EEEF/PID 268A) use physically separate transport paths. No cross-controller write path has been verified as safe.

Custom firmware direction: third-party repository `https://github.com/kei825/aula-l99-screen-fw` provides M*Core disassembler/emulator, LT168 MMIO model, and custom deck design, but omits proprietary Levetop engine/SDK components and cannot be treated as a standalone reproducible firmware build. No third-party firmware should be flashed without independent compatibility and recovery verification. Custom firmware is not claimed as a safe path.

**Current CFG and JMPI evidence status (2026-11-14)**:
- HEAD: `13b1ff06d99c837a1c2690ae897f84d27a51db66` (`main...origin/main [ahead 2]`, tracked tree clean; `analyze_pending.py` untracked).
- Accepted CFG checkpoints remain unchanged: 4096 baseline (`3ec58fd` implementation, `0387967` documentation), accounting repair (`59696c1cac8c597427374af176fef9e2ab6859bd`), 8192/512, 8192/1024, 12288/1024, and 12288/1536 (`9c1204152ad56987250b8d9ad1aaec19f1dedcd7`, `PASS_BUDGET_TRUNCATED`, binding `max_instructions`, reconciliation PASS, deterministic run1==run2). `DEFAULT_BUDGETS` unchanged; no roots added; existing accepted CFG artifacts unchanged.
- JMPI evidence implementation (committed): literal-pool helper `89ca1201ec8ff94497df7d8be68f260b9ff87b58` (`scripts/research/mcore_literal_pool.py`, `tests/test_mcore_literal_pool.py`); standalone deterministic post-processor `8b0b47a51db719721d36bb029de4a4dec7011fd6` (`scripts/research/jmpi_evidence_postprocess.py`, `tests/test_jmpi_evidence_postprocess.py`), independent of CFG traversal.
- JMPI literal-pool evidence (artifact `local_analysis/cfg_experiments/jmpi_evidence_postprocess/jmpi_literal_pool_evidence.json`, SHA-256 verified `B4D4D323E8B948F1D87D6DB008A016049B6C2D728CA78B595A2D14DC903C1AA3`): 52 unresolved indirect-flow sites; 49 validated JMPI literal targets; 3 register-indirect sites preserved; 15 unique literal targets; 0 invalid literal targets; deterministic output. Canonical membership for validated literal-target records: 23 `BLOCK_START`, 1 `INSIDE_BLOCK`, 25 `NON_CANONICAL` (record-level vs unique-target counts distinguished).
- ROM jump-table research (recorded): indirect jump site `0x6004D68A`, ROM table base `0x60016458`, 11 candidate entries (index 0–10), common join `0x6004D742`; all 11 cases write a 32-bit constant to `0x0086EF40`; default path writes `0x0001C200`. ISA semantics decoder-dependent. `0x0086EF40` cross-reference audit incomplete (output-limit interruption); hardware register purpose not claimed.
- Cleanup: legacy traversal-integrated JMPI mode RETIRED; backup `C:\temp\aula-l99-jmpi-legacy-backup.patch` SHA-256 `01CA8DD905211502A77FC4620B1BDEF411253AFB9FDB6E01E31F427BB08F659F`.
- Historical JMPI checkpoint tests: `python -m pytest tests -q` → 356 passed (12.74s). Full-root `pytest -q` has external `tools/Aula_L99_Linux-main/...` collection issues outside repo test scope.
- Decision gates: Literal-pool helper ACCEPTED; Standalone post-processor ACCEPTED; Legacy integrated JMPI mode RETIRED; CFG budget expansion HOLD; Resolved-edge integration HOLD; Type 3 investigation HOLD; Hardware flashing NO-GO.
- Next research: bounded `0x0086EF40` cross-reference audit; screen-control protocol research; independent ISA verification when needed.
- Generated experiment artifacts remain ignored local files under `local_analysis/cfg_experiments/`. Ubuntu/Ghidra remains an independent verification environment.

## Goal / Project objective

Open-source AULA L99 screen/controller research aimed at turning the built-in 320x480 touchscreen into a Stream Deck-style control surface. The approach is firmware-free (input bridge first), safety-first and read-only by default. Native page/widget and runtime-feedback research is documented separately; no hardware write is permitted under the current NO-GO decision.

- Turn the AULA L99 320x480 touchscreen into a Stream Deck-style controller.
- Preserve the stock touch-to-keyboard logic where practical.
- Replace or redesign the built-in Mini Numpad page with custom visual controls.
- Use a Windows background bridge to map existing NumPad events to PC actions.
- Later support short dynamic status fields through safe runtime RAM updates.

## Hardware architecture

Two controllers drive the device:

Keyboard side:
- USB HID controller: VID 0C45, PID 800A in wired mode.
- Standard keyboard HID events.
- Physical keyboard, lighting, wireless modes, and screen-to-keyboard event forwarding.
- Three-mode keyboard behavior includes wired, 2.4 GHz, and Bluetooth.
- The exact version source shown on the About page remains unresolved and must not be assumed to be the screen firmware version.

Screen side:
- USB device: VID EEEF, PID 268A.
- Windows CDC/serial interface, typically exposed as a COM port.
- 320x480 touchscreen.
- Built-in local page and resource engine.
- LT168-family controller firmware.
- HFD Code V2.3 architecture fingerprint: little-endian M*Core is the strongly supported working architecture, based on structural and third-party implementation evidence (not Levetop vendor-confirmed).

Keyboard events and screen runtime updates use different transport paths.

## Verified firmware components

1. HFD_Code_V2.2.bin and HFD_Code_V2.3.bin — Screen MCU executable logic.
2. UartTFT-II_Flash.bin — Screen pages, images, descriptors, touch records, animations, and transitions.
3. Keyboard MCU firmware — Separate from the screen MCU and screen resource image.

Verified factory reset payloads:

Official reset ZIP:
- Size: 45080624 bytes
- SHA-256: e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3

UartTFT-II_Flash.bin:
- Size: 127599044 bytes
- SHA-256: 4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4

HFD_Code_V2.2.bin:
- Size: 305800 bytes
- SHA-256: 432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf

HFD_Code_V2.3.bin:
- Size: 313652 bytes
- SHA-256: a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03

Same-named firmware files may contain different builds and must be identified by hash, not filename.

Do not redistribute these vendor files.

## Factory UI inspection

- 30 pages
- 385 display records
- 187 touch records
- 1138 icon descriptors
- 811 unique decoded images
- 3 animations
- 134 animation frames
- 26 wider-image decode issues recorded in the manifest, primarily invalid-bounds descriptor candidates
- Page 21 rendered successfully

## Mini Numpad mapping

Page 21 has 11 display records and 18 touch records. Seventeen are type 0xC001 action records. One is a type 0x8001 Home/back navigation record.

Home/back uses return value 0x0020 and goto page 1. NumPad action goto_page is 65535. Descriptor range is decimal 319 through 352, hexadecimal 0x013F through 0x0160.

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

## Image upload protocol

The obsolete claim that images are standard JPEG buffers with a 64-byte header is removed.

Verified information:
- Official captured photo upload contains 154 logical chunks.
- 150 chunks are 2060-byte data packets.
- Four are short control or commit commands.
- Total captured stream is approximately 309071 bytes.
- The image payload is not standard JPEG.
- Upload and built-in UI resources are separate paths.
- Normal image upload targets photo/background/GIF flash regions and does not overlay the active Mini Numpad page.
- The screen acknowledges packet transfers, but ACK does not prove address safety.

Known risk:
- Oversized writes can be acknowledged and still overwrite adjacent flash content.
- Unknown addresses, force overrides, and raw write replay remain unsafe.
- Do not claim later third-party guards make writing completely safe.

## Upload performance

Official application:
- Approximately 1.205 seconds.
- 150 x 2060-byte USB Bulk OUT transfers.

Current Python replay:
- Stable verified run: 41.616 seconds with 151 ACKs.
- Slower baseline: 67.708 seconds with 150 ACKs.

Root cause:
- Current replay splits each 2060-byte logical packet into approximately 33 synchronous 64-byte pyserial writes.
- Each 64-byte write is artificially paced.
- This transport architecture cannot approach official speed.
- The 115200 CDC line-coding value is not a reliable physical throughput limit for this USB bulk implementation.

Next transport milestone:
- Implement scripts/replay_captured_screen_win32.py.
- Use native Windows overlapped I/O.
- Submit complete 2060-byte logical packets.
- Read acknowledgements asynchronously.
- Do not change the installed USB driver.
- Do not use Zadig, WinUSB, or libusbK in the first implementation.
- On any write timeout, stop and require a device power cycle before another live test.

## Safety status

HARDWARE WRITE STATUS: NO-GO

NATIVE ANALYSIS STATUS: GO for bounded M*Core control-flow discovery.

NOT GO for claiming that the Type 3 dispatcher, Type 3 runtime mapping, or icon-selection formula has been established.

Unresolved:
- exact user-unit screen-controller revision
- modified-resource acceptance
- full updater write scope
- interrupted-write recovery
- independent verification of third-party recovery claims

- Original vendor images are immutable local references.
- No firmware write from this repository should be treated as safe by default.
- No unknown flash addresses.
- No force mode.
- No arbitrary erase/write replay.
- No firmware update during extraction or inspection.
- No claim of universal brick recovery.
- The official reset package is not a raw NAND dump.
- It does not include verified per-device OOB, ECC, bad-block, calibration, or unique-board data.
- About-page V1.31 is an unresolved whole-device display version and must not be assumed to identify the screen resource image, HFD image, or PC updater.

## Tooling: read-only descriptor inspector

`scripts/inspect_l99_descriptor.py` is a read-only, offline descriptor-mapping tool for the factory
AULA L99 screen resource image (`UartTFT-II_Flash.bin`). It never opens USB, COM, or HID, never
imports serial/USB/HID/updater modules, and never modifies the source image.

Placeholder usage (page / return-code mode; does not imply vendor images are included):

    python scripts/inspect_l99_descriptor.py `
        --image <path-to-UartTFT-II_Flash.bin> `
        --manifest <path-to-manifest.json> `
        --page 21 `
        --return-code 0x003B `
        --output <empty-output-directory>

Direct descriptor mode:

    python scripts/inspect_l99_descriptor.py `
        --image <path> `
        --manifest <path> `
        --descriptor 341 `
        --descriptor 342 `
        --output <empty-output-directory>

See `tests/test_inspect_l99_descriptor.py` for synthetic-test coverage (no vendor firmware embedded).

## Tooling: Address Xref Scanner

`scripts/research/hfd_address_xrefs.py` is a bounded deterministic offline scanner for references
to a target address (default `0x0086EF40`) in `HFD_Code_V2.3.bin`. It performs raw byte-pattern
scanning for the little-endian 32-bit representation and bounded local instruction-context
inspection of the immediate 2-byte instruction word. It does NOT perform recursive disassembly,
CFG traversal, or instruction validation. Raw byte-pattern matches are clearly distinguished from
verified instruction references.

Usage:

    python scripts/research/hfd_address_xrefs.py

Output includes firmware verification (size and SHA-256), raw match list with file offsets and
image addresses, and local instruction-kind classification (`jmpi`, `jsri`, `other`, `unaligned`,
`truncated`). Prohibited range `0x60031198-0x600315D0` is flagged.

Acceptance: **ACCEPT_WITH_LIMITATIONS** — raw byte-pattern scan only; instruction references
require full CFG validation not performed here.

## Tooling: offline NumPad icon patcher

`scripts/patch_l99_numpad_icon.py` is an offline-only ARGB4444 encoder and working-copy
patcher for the Page 21 NumPad 1 icons (descriptors 341 normal, 342 pressed). It:

- Requires exact factory size (127599044) and SHA-256
  (4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4).
- Never modifies the factory image; writes a separate patched working copy.
- Encodes two 67x67 RGBA PNGs (`--normal`, `--pressed`) as the verified ARGB4444 record.
- Performs a byte-for-byte round-trip check on factory descriptors 341/342 before patching.
- Writes only the two verified ranges:
  - 0x0077C446 .. 0x0077E757 (descriptor 341, unpressed)
  - 0x0077E758 .. 0x00780A69 (descriptor 342, pressed)
- Preserves all other bytes exactly and never touches touch records or descriptor-table entries.
- Never opens USB, COM, HID, or any updater.
- Generates: patched image, patch_report.json, diff_ranges.json,
  normal_encoded.bin, pressed_encoded.bin, normal_roundtrip.png, pressed_roundtrip.png.

See `tests/test_patch_l99_numpad_icon.py` for synthetic-test coverage (no vendor firmware
required or embedded).

## Tooling: Offline Runtime Frame Codec

`scripts/research/l99_runtime_frame_codec.py` is a deterministic offline encoder/decoder for
the documented AULA L99 short runtime USB protocol (frame format `5A A5 | length:u8 | body | CRC16:LE16`).
It supports read opcode `0x03` (word_address:BE16, word_count:BE16, max 8 words) and write opcode
`0x10` (word_address:BE16, word_0:BE16...). Address range 0x0000–0xFFFF. CRC16/MODBUS (poly 0xA001,
init 0xFFFF). No hardware access, no external dependencies. Includes round-trip tests and error cases.

Acceptance: **ACCEPT** — offline implementation complete with deterministic round-trip validation.

## Tooling: Capture Frame Classifier

`scripts/research/l99_capture_frame_classifier.py` is a deterministic offline classifier for
existing AULA L99 USB capture payloads (CSV exports only). It classifies frames into
`VALID_RUNTIME`, `INVALID_RUNTIME`, `UNVERIFIED_LARGE_PAYLOAD`, `UNKNOWN`, and
`CRC_VALID_UNSUPPORTED_OPCODE`. Includes endpoint attribution via capture-local device mapping
for known captures (e.g., `aula_home_numpad_transition`). Bounded memory, no hardware access.

Acceptance: **ACCEPT_WITH_LIMITATIONS** — operates on existing CSV captures only; no live
capture capability; device addresses are capture-local and not generalizable.

## Tooling: Win32 Photo Frame Uploader with Dynamic COM Discovery

`scripts/replay_captured_screen_win32.py` is the Win32 overlapped I/O uploader for the verified
Photo Frame upload stream (`aula_payload_hex.txt`). It uses native Windows overlapped I/O to submit
complete 2060-byte logical packets asynchronously, matching the official application's transfer
architecture.

### Dynamic COM Port Discovery (VID:PID EEEF:268A)

The uploader automatically discovers the AULA L99 screen controller's virtual COM port by querying
Windows Plug and Play inventory for `USB\VID_EEEF&PID_268A`. Discovery:

- Does **not** open the COM port
- Does **not** send any data to the device
- Does **not** require administrator rights (standard Windows inventory access)
- Is **fail-closed**: zero or multiple matches raise actionable errors
- Ignores the keyboard HID device (VID:PID 0C45:800A) and unrelated USB serial devices

### CLI Usage

```powershell
# Automatic discovery (recommended)
python scripts/replay_captured_screen_win32.py --input aula_payload_hex.txt --quiet

# Explicit port override
python scripts/replay_captured_screen_win32.py --port COM8 --input aula_payload_hex.txt --quiet

# Discovery only (prints resolved COM port, exits without loading payload or opening port)
python scripts/replay_captured_screen_win32.py --detect-port
```

### Discovery Behavior

| Scenario | Behavior |
|----------|----------|
| Exactly one EEEF:268A COM port found | Uses that port automatically |
| Zero EEEF:268A COM ports found | Exits with error: "No EEEF:268A screen controller COM port found. Use --port COMx to specify manually." |
| Multiple EEEF:268A COM ports found | Exits with error listing candidates: "Multiple EEEF:268A COM ports found: COM3, COM5. Specify --port explicitly." |
| Keyboard device (0C45:800A) present | Ignored (not the target) |
| Unrelated USB serial devices | Ignored |

### Discovery-Only Mode

`--detect-port` performs discovery and prints only the resolved COM port to stdout on success,
then exits with code 0. It does **not** load the payload, create the transport, or send any data.

### Safety Notes

- The hard-coded `COM8` default has been removed. The runtime never silently falls back to COM8.
- The keyboard device VID:PID 0C45:800A is explicitly excluded from discovery.
- Discovery uses PowerShell `Get-CimInstance` against `Win32_PnPEntity` with `-NoProfile -NonInteractive`.
- All tests are offline with mocked inventory; no COM port is opened during testing.

## Tooling: USB Device Attribution Utility

`scripts/research/l99_usb_device_attribution.py` is a deterministic offline utility that
extracts capture-local USB device address to VID/PID mappings from existing USB descriptor
evidence (pcapng via tshark). Verifies capture SHA-256 before processing. Preserves
capture-local device addresses; does not generalize across captures. Targets device addresses
6, 13, 15, 16 from `aula_home_numpad_transition.pcapng` (SHA-256 `B4DAD6E1...`).

Acceptance: **ACCEPT_WITH_LIMITATIONS** — requires tshark/Wireshark; capture-local addresses
only; no live USB access; output is capture-specific.

## Tooling: bounded canonical M*Core CFG (research, ignored local artifacts)

`scripts/research/hfd_cfg.py` is a read-only, offline, bounded recursive M*Core CFG
utility for `HFD_Code_V2.3.bin`. It reuses the local third-party `mcdis.py` decoder for
instruction decoding and never modifies the input binary. All generated output is written
under `local_analysis/cfg/` and is ignored by Git (local artifacts only).

`tests/test_hfd_cfg_partition.py` provides 99 standard-library unit tests covering canonical
partitioning, edge remap/validation, byte accounting, evidence classification,
acceptance-status determination, queue accounting, reconciliation, and comparison
generation. No vendor firmware is embedded in the tests.

Acceptance status `PASS_BUDGET_TRUNCATED` means the bounded observed graph is internally
canonical and reproducible, but traversal stopped because the instruction budget was
exhausted. The graph is accepted as bounded, correct within its scope, and not
complete-firmware coverage.

### Queue-accounting output schema

Canonical and reproducibility outputs now include a deterministic, machine-readable
queue-accounting section. The shared helper `build_queue_accounting()` produces:

- `queue_discovery_records` — deterministically sorted records, each containing
  `target_address`, `call_site_address`, `depth`, `work_type`, `reason`, `function_id`,
  and `final_status`; absent values are represented as `null`.
- `queue_discovery_record_count`
- `queue_final_status_counts`
- `pending_block_work`, `pending_block_work_count`
- `pending_function_work`, `pending_function_work_count`
- `pending_total_work`, `pending_total_work_count`
- `processed_or_resolved_queue_records`
- `repeated_queue_discovery_count`
- `queue_reconciliation_status`

`reconcile_queue_accounting()` enforces all queue-accounting equations
(`processed_or_resolved + pending_total == discovery_record_count`) before output is
written, and fails loudly on mismatch.

### Comparison CLI

`generate_comparison_4096_vs_8192()` and the following CLI options compare a baseline
canonical summary against an experiment canonical summary:

- `--compare-baseline-json <path>` — baseline canonical summary JSON.
- `--compare-experiment-json <path>` — experiment canonical summary JSON.
- `--compare-output <path>` — output path for the comparison JSON.

Comparison output includes explicit provenance paths for both inputs and fails loudly when
required fields are missing. Optional unavailable metrics use `null` together with
`value_present: false` and a `reason`. Candidate-versus-queue metrics
(`queued_candidates_scheduled_pending`, `queued_candidates_not_scheduled_depth_limit`,
`queued_candidates_without_function_work_record`) are reported for both sides.

### Binding-budget exhaustion

Block-loop exhaustion now reports the actual exhausted budget reason, for example
`budget_max_basic_blocks`, instead of the hardcoded `budget_max_instructions`. Generic
`budget_*` reasons and `pending_unprocessed_budget_exhaustion` are classified as
`pending_budget_exhaustion`.

Independent cross-validation was performed with Ghidra `analyzeHeadless` and the third-party
ghidra-mcore processor (MCORE:LE:32:default) on an Ubuntu x86_64 host. This Ghidra
verification confirmed startup literals, two direct-call targets (`0x600174B8 -> 0x60045150`
and `0x600174BA -> 0x600449B0`), and the self-loop `0x600174BC -> 0x600174BC`. ABI
correctness of the patched Ghidra compiler spec remains unknown, and decompiler
parameter/return/calling-convention conclusions are not treated as verified. Full-firmware
coverage is not claimed.

See `docs/PROJECT_HANDOVER.md` for full implementation detail, metrics, and evidence
classification.

## Repository contents

Only files tracked by Git are described here. Local ignored vendor binaries are not included.

Tracked: scripts, analysis tools, protocol notes, changelog, and handover documentation.

Local and ignored only: official firmware, captures, dumps, decoded assets, reset ZIPs, and third-party repositories.

## Current roadmap

1. Consolidate documentation.
2. Resolve descriptor 341/342 to source offsets, formats, dimensions, and allocations.
3. Build an offline-only single-button patcher.
4. Patch a working copy only.
5. Re-run independent inspection and byte-level diff.
6. Preserve all Page 21 touch records and screen commands.
7. Implement native Win32 overlapped uploader.
8. Validate recovery and package compatibility.
9. Only then consider a controlled hardware write.

## Screen-Control Evidence Inventory

`docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md` — Consolidated inventory of USB-only screen-control
evidence from accepted offline research checkpoints. Includes:

- Verified USB device interfaces (keyboard HID 0C45:800A, screen CDC EEEF:268A)
- Verified image upload behavior (154 chunks, 2060-byte packets, not JPEG, flash slots only)
- Runtime RAM protocol evidence (short runtime frame codec from Levetop reference — **UNVERIFIED on user unit**)
- Touch event transport (screen Mini Numpad → PC via keyboard HID, return codes 0x0030–0x0040)
- Runtime display-update limitations (no live framebuffer RAM write verified, no visible LCD update verified)
- Page-switch evidence status (Page 21 VERIFIED; 0x7000 system switching Levetop reference only)
- GT911 evidence status (public teardown only — NOT on user's unit)
- LT168/LT268 identity uncertainty (user's unit unopened, exact silicon UNVERIFIED)
- Hardware safety restrictions (NO-GO, critical blockers: image-level self-checksum UNKNOWN, UI-only package acceptance STRONG_INFERENCE, interrupted-write recovery UNKNOWN)
- Open feasibility questions and recommended evidence for next USB-only milestone

Acceptance: **ACCEPTED** — documentation sync checkpoint.

## Companion Integration (offline development only)

Bitfocus Companion is the preferred first external platform for the AULA L99 input bridge. The offline Companion integration (input-only integration) maps existing Mini Numpad HID events to Companion button press actions through a local bridge. It does not require firmware modification, flashing, or any hardware access.

### Scope and readiness

- Safe for offline development and testing: unit/integration tests, dry-run development with DryRunProvider, mock transport validation, and mapping configuration validation.
- Companion is strictly opt-in and disabled by default. Activation requires both the CLI flag and a JSON config file; the default runtime path still uses `MockTransport` and opens no sockets.
- Not yet suitable for production deployment with live Companion, unattended operation without monitoring, or networks where loopback isolation is insufficient.
- No claim of production readiness is made. Live Companion behavior has not been independently validated. Production use requires authentication support (if Companion requires it), a health check endpoint before dispatch, a circuit breaker for repeated failures, HTTPS consideration for defense-in-depth, and a live integration test with real Companion 5.2.0+.

### Companion modules (untracked, new since baseline)

| Module | Purpose |
|--------|---------|
| `src/aula_bridge/companion_types.py` | Shared `ButtonLocation` frozen dataclass (page, row, column). |
| `src/aula_bridge/companion_optin_config.py` | Strict JSON opt-in configuration loader. Validates `enabled`, loopback `host`, `port`, `timeout`, and `mapping_file`; missing file yields the disabled default. No network, no hardware access. |
| `src/aula_bridge/companion_button_mapping.py` | Strict JSON mapping loader: logical numpad key → `ButtonLocation`. No network, no hardware access. |
| `src/aula_bridge/companion_dispatch_adapter.py` | Adapter connecting ActionDispatcher to Companion HTTP Core. Processes only `short_press` events. |
| `src/aula_bridge/companion_http_transport.py` | HTTP transport core for Companion 5.2.0 press API. Dependency-injected sender. No retries, no buffering, no background threads. |
| `src/aula_bridge/companion_http_sender.py` | Security-hardened `urllib` sender. HTTP POST only, loopback-only (`127.0.0.1`), `http://` scheme only, no redirects, no credentials, no proxy. |
| `src/aula_bridge/companion_dispatch_worker.py` | Bounded asynchronous dispatch worker. Exactly one daemon thread, FIFO queue capacity 8, non-blocking admission, overflow and shutdown-drop accounting. |
| `src/aula_bridge/companion_transport.py` | `MockCompanionTransport` for offline testing. Records dispatched requests in order. No network I/O. |

### Verified safety properties

- **Short-press only:** `CompanionDispatchAdapter` processes only `short_press` events; `hold`, `secondary_hold`, `key_down`, `key_up`, `repeat_ignored` are ignored (zero HTTP requests).
- **Hold suppression:** All hold-type events produce zero HTTP requests; no command or payload reaches the transport.
- **Device identity preserved:** `ProviderEvent.device` is never mutated; logged in INFO logs and included in transport metadata.
- **Event sequence preserved:** `ProviderEvent.seq` is never mutated. The Worker snapshots each event with `dataclasses.replace()` at enqueue time, so later caller mutation cannot affect queued data. FIFO order is preserved. (`ProviderEvent` itself is a mutable dataclass; immutability is enforced by convention and by the Worker snapshot, not by `frozen=True`.)
- **HTTP response logging:** Adapter logs key, device, seq, event, status_code, success, error_code; all status codes mapped to semantic error codes (200→success, 204→NO_CONTROL, 400→INVALID_LOCATION, 403→FORBIDDEN, 4xx→CLIENT_ERROR, 5xx→SERVER_ERROR, others→UNEXPECTED_STATUS).
- **HTTP failure handling:** All non-200 responses produce `HttpResponse(success=False)`; no exceptions propagate; all error paths caught and converted.
- **No default button mappings:** `load_companion_button_mapping` requires an explicit mapping file; empty mappings return an empty `MappingProxyType`; no automatic/default locations invented.
- **Strict JSON validation:** Duplicate JSON keys rejected; version must be integer (version 1 only); all location fields (page, row, column) must be genuine integers (bool/float/string rejected); negative values rejected; unknown logical keys rejected; extra fields rejected; missing required fields rejected; top-level JSON must be object; mappings must be object.
- **No automatic retries:** Transport makes exactly one call to sender; sender makes exactly one `opener.open()` call; redirects rejected (`_NoRedirectHandler` returns `None` for all redirect codes).
- **No stale event replay:** Worker shutdown drops queued events without re-queueing them; a late `send()` after shutdown is rejected and counted.
- **Bounded Worker queue:** FIFO `queue.Queue(maxsize=8)`. Admission uses non-blocking `put_nowait()`; a full queue drops the incoming event, increments `overflow_count`, and logs a WARNING.
- **Drop accounting:** `overflow_count` and `shutdown_drops` are independent counters, both readable at runtime.
- **No accidental live network activation:** All tests use fake/mock senders; sender validates host is loopback before any connection; non-loopback hosts rejected; only `http://` scheme allowed (`https://`, `ftp://`, `file://`, `ws://` rejected).
- **No firmware/hardware access:** Zero imports of `serial`, `usb`, `hid`, or hardware libraries; pure Python with dependency injection; transport protocol is abstract interface with no I/O.
- **No modification of accepted Bridge behavior:** `ActionDispatcher`, `ProviderEvent`, and `DryRunProvider` are unchanged; the Companion adapter and Worker implement the `Transport` protocol.
- **DryRunProvider preserved:** The default and Companion paths both use `DryRunProvider`; enabling Companion does not remove dry-run logging.
- **No hidden port dependency:** Default Companion HTTP port is `8000`; host and port are required explicitly in the transport constructor (defaults `127.0.0.1:8000`, overridable). E2E tests use an explicit test port (never assume 5000 or 8000).

### Activation contract (CLI + JSON dual gate)

- `--enable-companion` and `--companion-config PATH` must be supplied together; supplying only one is an error and exits with status 1.
- The JSON config must set `companion.enabled = true`. A config with `enabled=false`, or a missing config file, does not enable Companion.
- `enabled=true` requires an explicit `mapping_file`; the mapping file must exist and pass strict validation.
- Invalid config, invalid mapping, unreadable files, or transport construction errors fail fast with exit code 1. No partial Worker is left running.
- Without both flags, the bridge uses `MockTransport` and logs that Companion is disabled.

### Bounded Worker architecture

- `build_companion_transport()` constructs `CompanionHttpSender` → `CompanionHttpTransport` → `CompanionDispatchAdapter`, then wraps the adapter in a `CompanionDispatchWorker` (queue capacity 8).
- The Worker, not the raw adapter, is injected into `ActionDispatcher`. The Windows Raw Input message-loop thread only performs non-blocking queue admission; it never performs HTTP I/O.
- Exactly one daemon worker thread dequeues FIFO and calls `transport.send()`. Worker exceptions are isolated and logged; one failed event does not kill the worker.
- Worker `send()`/`close()` share a lock so a late `send()` cannot enqueue after shutdown drains the queue.
- Startup failure after Worker construction is repaired by closing the Worker; the dispatcher-initialization path also closes the Worker if dispatcher setup raises.

### Shutdown lifecycle

- The message loop is wrapped in `try/finally`.
- Shutdown order is `dispatcher.close()` (which calls `Worker.close()`) then `provider.close()`; `provider.close()` runs even if `dispatcher.close()` raises.
- `Worker.close()` is idempotent: it rejects new events, drains and counts pending events as shutdown drops (never replaying them), then attempts a bounded join (default 5 s) without holding the lock.
- An in-flight HTTP request cannot be forcibly cancelled. If the worker is still alive after the bounded join, that state is logged as a WARNING and a full shutdown is not falsely claimed.

### Offline testing and acceptance status

- Offline unit, integration, runtime-observability, and startup-failure-injection tests pass (see CHANGELOG and `docs/PROJECT_HANDOVER.md`).
- Acceptance is limited to offline development and testing. Live Companion behavior has not been independently validated.
- No production readiness is claimed.

### HTTP Sender Security (verified)

- **Redirect rejection:** `_NoRedirectHandler.redirect_request` returns `None` for all redirect codes (301, 302, 303, 307, 308); no follow-up requests.
- **Scheme validation:** Only `http://` permitted; `https://`, `ftp://`, `file://`, `ws://` rejected as `INVALID_URL`.
- **Userinfo rejection:** Username/password in URL rejected; credentials never appear in error messages.
- **Path/query/fragment restriction:** Fragment (`#section`) and query parameters (`?foo=bar`) rejected; path must match `^/api/location/(\d+)/(\d+)/(\d+)/press$`; wrong path or missing `/press` suffix rejected.
- **Loopback-only restriction:** Sender validates host is loopback via `ipaddress.ip_address().is_loopback`; `127.0.0.1` allowed; `localhost` rejected (not numeric IP); remote IPs and domains rejected.

### Remaining risks (not resolved)

| Risk | Classification | Details |
|------|----------------|---------|
| No integration test with real Companion instance | UNKNOWN | All tests use fakes; real API behavior (rate limits, auth, schema changes) untested; live Companion behavior not independently validated |
| Button mapping file not hot-reloadable | INFERENCE | Mapping loaded once at startup; file changes require restart |
| No authentication support | INFERENCE | Companion HTTP API may require auth token; not implemented |
| HTTP executes on the dedicated Worker thread | VERIFIED | HTTP requests run synchronously inside the Worker thread, not on the Windows message-loop thread; the message loop only enqueues |
| In-flight HTTP cannot be forcibly cancelled | VERIFIED | A blocking request finishes or times out; shutdown uses a bounded join and does not kill the thread |
| No health check / connection verification | INFERENCE | No pre-flight check that Companion is reachable before dispatch |
| Error codes not mapped to user actions | INFERENCE | Logs errors but no retry/backoff/alerting strategy defined |
| No encryption (HTTP only) | VERIFIED | `http://` only; loopback mitigates but not defense-in-depth |
| Fixed 5s default timeout | INFERENCE | May be too short for slow networks / loaded Companion |
| No circuit breaker | INFERENCE | Repeated failures don't pause dispatch; could log spam |

## Attribution

- softce/aula-l99-research for the verified factory reset extraction offsets, hash-locked extractor, UI parser, page/resource research, and demonstrated custom UI approach.
- gavindi/Aula_L99_Linux for extensive keyboard and screen protocol research, Linux tools, captures, and upload format work.
- mos9527/evbunpack for Enigma Virtual Box extraction work.

Do not imply that third-party firmware or artwork is licensed by this repository.

## Current verified capabilities

- Wired Raw Input attribution for VID 0C45 / PID 800A / MI_00 (verified; device-selection defect fixed so MI_00 is used)
- Bitfocus Companion v5.1.3 endpoint verified on localhost (POST /api/location/1/0/0/press returns HTTP 200); physical Companion E2E still pending
- Offline Page 21 UI prototype exists (320x480, 17 action zones, return codes 0x0030–0x0040)
- Deterministic RGB565 export exists (320x480, 307200 bytes, SHA-256 524b0dcd...); offline framebuffer conversion only
- Ubuntu REA automated full-firmware analysis pipeline operational (V1–V6); V6 has a local display-path call graph (0x600315D0 → 0x60049D98, STRONG_INFERENCE); host-to-display chain remains incomplete
- Full Firmware RE V7 planned (Indirect Entry / Address-Taken / Pointer-Table Audit), not started
- no claim that modified firmware has been safely flashed

## V9.2 validated collector status

V9.2 validates bounded evidence collectors only — not a confirmed LCD runtime display handler.

## AFRE Wave 2 research checkpoint documentation

**Wave 2: Real Ghidra extraction completed.** Real Ghidra 12.1.4 extraction completed against canonical firmware `HFD_Code_V2.3.bin` — 313,652 bytes, SHA-256 `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03`. Full extractor determinism reported PASS. Real coverage accounting completed: firmware_bytes 313,652; mapped_bytes 313,652 (100% mapped coverage); instruction_bytes 72,070 (22.98% instruction-byte density); defined_data_bytes 8,817; undefined_bytes 232,765; overlap_bytes 0; function_owned_instruction_bytes 34,764 (48.24%); unowned_instruction_bytes 37,306. Mapped coverage is distinct from instruction coverage — 100% mapped does not mean fully analyzed; 232,765 bytes remain undefined. SQLite reconciliation integration: PARTIAL.

**Accepted findings:** Page 21 schema VERIFIED (17 touch records, 19-byte descriptor schema, return codes 0x0030–0x0040, normal and pressed icon IDs verified); Corrected resource offsets VERIFIED (NumPad 1 header 0x00024CA9, payload 0x00024CAC; old offset 0x00024A81 contradicted); USB HID VERIFIED (Numpad 1 usage 0x59, Numpad 2 usage 0x5A, Numpad 3 usage 0x5B).

**Limitations:** Companion PARTIAL (physical Companion E2E UNVERIFIED); HardwareMonitor PARTIAL (INI-to-HID complete dataflow UNRESOLVED); LCD Runtime research UNVERIFIED (generic runtime icon update, host-controlled widget update, dynamic Stream Deck all unverified). Static Stream Deck MVP NOT claimed as complete.

#### Static Stream Deck MVP Part 2 — current status
- 17-button manifest created.
- Static icon preview report created.
- Resource patch dry-run report created.
- 49 focused tests passed.
- companion_button_mapping.json contains 17 mappings.
- Numpad 1/2/3 HID usages verified.
- Remaining 14 keys require physical verification.
- All 17 Companion locations remain provisional.
- No hardware deployment performed.

Current status: OFFLINE_MVP_COMPLETE / PHYSICAL_E2E_PENDING / DEVICE_DEPLOYMENT_NOT_AUTHORIZED

See `docs/PROJECT_HANDOVER.md` section 38 for full AFRE Wave 2 research checkpoint documentation.

- Session A computed-call collector (`V92ComputedCallCollector.java`): FIX_A_PASS; final SHA-256 `5F8E9E244F563AF18A243388E1BD50AD87EF3B65591BAD9C7B7B9F54A24835BF`; real Ghidra 12.1.4 validation passed; 9 call sites, 4 pointer cells
- Session B shared-state collector (`V92SharedStateCollector.java`): FIX_B_PASS_ON_DISPOSABLE_PROJECT (superseding FIX_B_PROJECT_INTEGRITY_FAILED); final SHA-256 `F256C3593C45F3684CB49DE506BC64C29F57EE37C5E39C4707AB1D391BEF22C6`; validated against a disposable full project copy after the original-project integrity incident
- Session C boundary collector (`V92BoundaryCollector.java`): FIX_C_PASS; final SHA-256 `56745F0A0B5898D549DBCDAE6A812F1778817A4208596AD8D8D19B785EF0A17E`; target `0x60049B90`; classification INSUFFICIENT_EVIDENCE (valid research result, not an execution failure)

Current research verdict: INSUFFICIENT_EVIDENCE. V9.2 has validated the bounded evidence collectors but has not established a confirmed LCD runtime display handler.

The validated collectors are distinct from the unvalidated final runtime package. The current integration package and ZIP were built before the final A/B/C collector fixes and must not be treated as runtime-ready. The immediate next step is to rebuild the integration package using the final validated A/B/C collectors and fix `run_v9_2.sh` (use `-process`, `-noanalysis`, `-readOnly`, pass `-scriptPath` separately, pass collector script name to `-postScript`, pass the output JSON path argument, use isolated Java script directories, scan the actual combined Ghidra log, publish every final deterministic artifact).

See `docs/PROJECT_HANDOVER.md` for detailed continuity, checkpoint information, A/B/C validation outcomes, exact remaining package-runner defects, Windows integration source locations, and REA evidence locations.

## Evidence and provenance

All findings are classified by evidence category:

**A. User-unit verified** — Directly observed on the user's own AULA L99, official files held by the user, or captures produced from that unit. Examples: wired Raw Input attribution for VID 0C45 / PID 800A / MI_00, factory UartTFT-II_Flash.bin size and SHA-256, HFD_Code_V2.2.bin and HFD_Code_V2.3.bin sizes and hashes, Page 21 Mini Numpad descriptor mapping, offline descriptor/patch tool round-trip validation.

**B. AULA vendor artifacts verified** — Derived from official AULA applications, installers, firmware packages, updaters, or official download sources. Examples: official reset package hash, official UartTFT-II_Flash.bin download, DeviceDriver.exe and ISP updater process hierarchy, Flash.ini flash-chip geometry database.

**C. Levetop official reference** — Derived from official Levetop documentation, LT168B SDK, LT168B MCU SDK, UI_Editor-II examples, or official compiled reference artifacts. Examples: LT168/UartTFT ecosystem compatibility, official widget families (icon, GIF, keyboard-key, page, variable), official LT168 memory map, startup/vector model, W25N01GV driver, compiled reference artifacts, official example supporting at least 90 pages, widget WriteAddr operations and system page switching through 0x7000.

**D. Public teardown evidence** — Derived from a publicly available AULA L99 teardown/review sample, not from the user's own keyboard. Examples: HFD168BDP screen controller marking, HFD80CP100 keyboard MCU, Winbond external memory, reported GT911 touch controller.

**E. Third-party research** — Derived from gavindi/Aula_L99_Linux or kei825/aula-l99-screen-fw. Categories D and E are never presented as direct evidence from the user's own unit.

## Primary external references

- **Levetop LT168 product documentation and official SDK/UI_Editor-II materials** — Official LT168/UartTFT reference ecosystem. Used for: official UI widget crosswalk (icon, GIF, keyboard-key, page, variable concepts), LT168 memory map, startup/vector model, W25N01GV driver, compiled reference artifacts, widget WriteAddr operations, system page switching through 0x7000, official example supporting at least 90 pages.

- **https://github.com/gavindi/Aula_L99_Linux/** — Provides substantial reverse engineering of keyboard HID protocol, RTC/system-monitor packets, screen image/GIF upload, serial transfer behavior, and Linux-side tooling. Its historical LT7689 wording is an engine-lineage or historical hypothesis, not confirmed chip identity, and is not adopted as confirmed for this project. Third-party real-hardware claims have not been independently reproduced on the user's unit.

- **https://github.com/kei825/aula-l99-screen-fw/** — Provides M*Core disassembler/emulator, stock HFD Code V2.2 emulation claims, LT168 MMIO model, GT911, W25N01GV, SCI1 and LCD models, custom 4x4 deck design, PC-side serial deck implementation, and detailed hardware/firmware notes. The repository omits proprietary Levetop engine/SDK components and cannot be treated as a standalone reproducible firmware build. No third-party firmware should be flashed without independent compatibility and recovery verification.

## Hardware identity

- A public AULA L99 teardown sample shows an HFD168BDP screen controller, HFD80CP100 keyboard MCU, Winbond external memory, and a reported GT911 touch controller. This is public teardown evidence, not from the user's keyboard.
- The user's own unit has not been physically opened.
- The user's firmware/resource artifacts show strong compatibility with the Levetop LT168/UartTFT ecosystem.
- Exact silicon identity and hardware revision of the user's unit remain unverified.

Do not state: the user's unit physically contains HFD168BDP; HFD168BDP is definitively identical to Levetop LT168B; the user's flash is definitively W25N01GV; the user's panel controller is definitively ST7796S.
