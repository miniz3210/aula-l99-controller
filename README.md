# AULA L99 Touchscreen Reverse Engineering and Stream Deck Bridge

Windows-oriented research and tooling for turning the AULA L99 keyboard touchscreen into a Stream Deck-style controller.

## Project status

This is an active reverse-engineering and prototyping project. The present milestone is:

- Factory screen resource image extracted from an official AULA reset package.
- UartTFT-II_Flash.bin independently verified by size and SHA-256.
- Factory UI parsed successfully.
- Page 21 confirmed as the built-in Mini Numpad.
- All 17 touch zones, return codes, rectangles, and normal/pressed icon descriptor pairs mapped.
- Offline-only ARGB4444 encoder and working-copy patcher added for NumPad 1 descriptors 341/342
  (scripts/patch_l99_numpad_icon.py). Factory image is never modified.
- HFD Code V2.3 target identity verified: 313,652 bytes, SHA-256 A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03.
- Type 3 is a 14-byte serialized UI record family with parsed fields: variable, x, y, first_icon, last_icon, min_value, max_value.
- Multi-state Type 3 records exist, disproving the earlier universal two-state claim.
- Little-endian M*Core is the strongly supported working architecture for HFD Code V2.3, based on structural and third-party implementation evidence (not Levetop vendor-confirmed).
- Existing third-party M*Core decoder (mcdis.py) has passed bounded structural validation across four regions (95% linear mnemonic coverage, 16/16 branch targets in-image and aligned).
- Native Type 3 runtime mapping and dispatcher remain unverified.
- No claim of safe firmware modification or flashing follows from this analysis.
- Current hardware-write status remains blocked pending offline patch validation and recovery review.

**Current CFG status (2026-11-13)**:
- The committed 4096 bounded graph (`3ec58fd` implementation, `0387967` documentation) remains the accepted baseline checkpoint.
- Accounting repair commit: `59696c1cac8c597427374af176fef9e2ab6859bd` — `fix: reconcile bounded HFD CFG queue accounting` (uncommitted).
- Accounting repair: ACCEPTED. Final acceptance PASS. Full unittest suite: 262 passing. CFG partition tests: 99 passing. Python compilation: PASS.
- Baseline artifacts unchanged. Target and decoder SHA256 unchanged. No prohibited-range access. No canonical overlaps. No duplicate canonical ownership or edges.
- 8192 bounded experiment: ACCEPTED. Root `0x60017490`, `max_instructions=8192`, binding budget `max_basic_blocks=512`. Acceptance `PASS_BUDGET_TRUNCATED`. Canonical blocks: 666. Canonical instructions: 5238. Accepted functions: 22. Candidates: 77. Queue discoveries: 223. Processed/resolved: 153. Pending blocks: 12. Pending functions: 58. Pending total: 70. Reconciliation: 153 + 70 = 223. Self-loop count: 1. Prohibited-range access: 0.
- Reproducibility: two independent fresh-directory runs, six matching artifact hashes. Comparison JSON SHA256: `92D61DD6CF5E9E965965218B9A7BDB9CCA107DDF1D3C20DAE2849FA7AA318310`.
- Decision gates: Increase `max_basic_blocks` HOLD. Change `DEFAULT_BUDGETS` HOLD. Add vector roots HOLD. Multi-root expansion HOLD. Type 3 investigation HOLD.
- Generated experiment artifacts remain ignored local files under `local_analysis/cfg_experiments/`.
- Ubuntu/Ghidra remains an independent verification environment; its startup-region checkpoint is retained.

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

## Attribution

- softce/aula-l99-research for the verified factory reset extraction offsets, hash-locked extractor, UI parser, page/resource research, and demonstrated custom UI approach.
- gavindi/Aula_L99_Linux for extensive keyboard and screen protocol research, Linux tools, captures, and upload format work.
- mos9527/evbunpack for Enigma Virtual Box extraction work.

Do not imply that third-party firmware or artwork is licensed by this repository.

## Current verified capabilities

- Wired Raw Input attribution for VID 0C45 / PID 800A / MI_00
- make-code-based screen Numpad mapping
- Num Lock-independent mapping design
- deterministic short/hold state machine
- dry-run provider architecture
- official UI widget crosswalk for icon, GIF, keyboard-key, page and variable concepts
- no claim that modified firmware has been safely flashed

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
