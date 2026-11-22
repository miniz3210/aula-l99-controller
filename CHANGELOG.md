

#### 2026-11-22 - U7.1-U7.5 and S1-S5 Product Direction Checkpoint

- **Product goal:** a true AULA L99 Stream Deck-style controller with Windows visual editor, arbitrary custom icons/layouts, independently identifiable touch actions, bidirectional feedback, profiles, and deployment/recovery. HID numpad remapping alone is not an acceptable final product.
- **Preferred architecture (development direction, not completed):** stock screen MCU runtime + custom UI/NAND resources + dedicated Windows touch/variable bridge + external open-source macro engine (Companion or Macro Deck). Custom MCU executable remains a fallback if stock runtime proves insufficient.
- **U7.1:** official image structure and record parsing carried forward; image-level header CRC rule reproduced offline for the known factory image (length at 0x174, CRC at 0x178, complement at 0x17C, bytes 0x174-0x17F blanked with FF during calculation). CRC reproduction does not establish bootloader/updater enforcement, full serializer semantics, or flash safety.
- **U7.2:** Page 22 Calculator contains 18 type 0xC001 button records plus navigation, and its emulator rendered the sequence `1`, `12`, `12+`, `12+3`, `15` after `=` (VERIFIED OFFLINE). The Calculator produces generic `41 FF FF 43 4C` UART frames on recorded steps rather than the Page 21 per-button IDs. Type 1 payload at UI offset 0x24E59 starts with 0x0218, but its runtime variable binding is UNRESOLVED.
- **U7.3-U7.5:** bounded RAM change observations and Ghidra focused analysis completed. U7.4 J04 compiled and ran after adding the missing `ghidra.program.model.scalar.Scalar` import (121,825 instructions, 255 matches, not truncated). U7.5 found no breakpoint hits in three preselected candidate functions; absence of hits is not absence of RAM writers. Actual Type 1 consumer, Calculator text writer and host variable-write command remain UNRESOLVED.
- **S1:** complete 30-page structural inventory (385 widgets, 187 touch records), but functional labels and firmware dependencies are not fully validated. Page 21 is Mini Numpad; Page 22 is Calculator. Page 19 is a dynamic-widget research candidate; Page 20 is Play. Empty-record pages 24/29 are not proven safe custom slots.
- **S2:** widget/touch blocks are packed without insertion gaps. Same-length replacement is structurally plausible only; relocation-based widget growth and page 30 addition remain HOLD. A Python parser's fixed page count does not prove a firmware hardcode.
- **S3:** zero direct 0x0218 operand/pcode matches in examined HFD V2.2 do not disprove indirect runtime variable lookup or a host update protocol. Host-controlled Type 1 widget remains UNRESOLVED, not disproven.
- **S4:** physical keyboard HID/Raw Input evidence supports a PC action bridge, but dedicated arbitrary touch ID transport and complete device-to-action correlation are not yet established. Page 21 17/17 touch-to-UART remains VERIFIED OFFLINE; do not conflate it with physical end-to-end validation.
- **S5:** recommendation REJECTED: mislabeled Page 21 as Calculator and Page 22 as Play, used outdated touch/CRC evidence, and produced a dependency matrix with nonstandard JSON hex literals. Do not use its rankings or page IDs as implementation input. No S5 rerun required.
- **External references:** kei825/aula-l99-screen-fw provides emulator/parser and tooling evidence; softce/aula-l99-research reports successful custom UI/NAND pages, touch records, and host-to-screen variable updates on a third-party device. Third-party results are not direct validation of this user's hardware or recovery.
- **Next milestone:** product-focused UI/NAND builder + emulator visual/touch regression, dedicated touch transport, dynamic feedback protocol, and controlled UI-only deployment/recovery gates. Preserve Page 21 as regression reference, not necessarily the final product page.
- **Safety:** official screen flashing has succeeded previously, but arbitrary modified UI flashing and custom MCU flashing are not authorized by this checkpoint. Physical custom flash remains NO-GO until image acceptance, target write scope and recovery evidence justify a separately approved controlled test.
- **Workflow:** bounded local REA jobs, max 80k agent tokens; retain useful reports under `C:\temp\aula-l99-controller\u76\s1` etc. No agent commits/pushes; owner controls Git operations.
# Changelog

## Unreleased

### 2026-11-21 - AutoResearch and UI/NAND U6

#### A. AutoResearch

- Established unattended Ubuntu REA research workflow.
- Completed AutoResearch v1-v5 research cycles.
- Implemented resumable local analysis and evidence gates.
- Used Ghidra 12.1.4, Python and MCore emulator.
- Reduced dependence on token-heavy interactive agents.
- Maintained read-only and no-flash safety boundaries.

#### B. Device Firmware Research

- Identified a 1396-byte RAM-relocated code block.
- Destination address: 0x00800000.
- Executable entry: 0x00800004.
- V2.2/V2.3 relocated bytes match.
- Strong static evidence supports a serial-flash-style programming routine.
- Observed command-like values 0x06, 0x05 and 0x02.
- Observed 24-bit address transfer.
- Observed 256-byte page-boundary splitting.
- Physical flash partition and recovery protection remain unresolved.

#### C. UI/NAND Research U1-U5.1

- Official UI image contains 30 pages, indices 0-29.
- Corrected the 12-byte page record structure.
- Widget record header is 5 bytes.
- Touch record header is 3 bytes.
- Record type uses little-endian 16-bit values.
- Payload length uses the final header byte & 0x7F.
- Decoded 385 widget record boundaries.
- Decoded 187 touch record boundaries.
- Achieved 30/30 widget and touch record round-trips.
- Corrected the earlier invalid inferred touch pointers.

#### D. U6 Touch Validation

- Page 21 contains 18 touch records.
- 17 Type 0xC001 button records.
- One Type 0x8001 navigation record.
- All 17 button records matched expected emulator events.
- Event IDs range from 0x30 to 0x40.
- UART body format: 41 FF FF 00 XX.
- Navigation record changed Page 21 to Page 1.
- Classification: VERIFIED OFFLINE.
- Physical hardware transport remains unverified.

#### E. Safety

- No custom firmware flashed.
- No custom UI image flashed.
- Independent recovery remains unresolved.
- Physical flash protection boundaries remain unresolved.
- Custom firmware flashing remains NO-GO.

### AULA L99 screen research summary (2026-11-20)

#### Confirmed
- Open-source screen-firmware direction identified: https://github.com/kei825/aula-l99-screen-fw (M*Core disassembler/emulator, LT168 MMIO model; omits proprietary Levetop engine/SDK components; not a standalone reproducible firmware build; no third-party firmware should be flashed without independent verification).
- Chinese AULA software version 1.0.1.4 confirmed as the only verified baseline exposing both keyboard and screen firmware upgrade as separate paths targeting different controllers.
- Keyboard (USB HID VID 0C45/PID 800A) and screen (CDC VID EEEF/PID 268A) firmware paths remain explicitly separate; no cross-controller write path verified as safe.
- Official screen updater L99_ISP_CNUI_V1.23_156.exe successfully launched with Fn+X+0+6 to enter screen update mode (bootloader COM4); evidence only — no custom firmware flashed.
- DeviceDriver.exe/HardwareMonitor telemetry writes to C:\Program Files (x86)\AULA L99\data.ini (CPU_Temperature/GPU_Temperature).
- LT168B NOT confirmed hardware; teardown photos show HFD168BDP screen controller marking; relation to Levetop LT168B is inference.
- Screen sub-board SI-2686-TFT-3.98 V01; flash Winbond 25N01GV; touch IC Goodix GT911; SW2 push switch; four test pads (probably PGMCK/PGMIO/RST, not verified by continuity).

#### Safety
- Hardware flashing: NO-GO. SAFE_FLASH_NOT_READY. Preserve official path; do not flash speculative/custom image; establish image layout/checksums/target memory regions/page counts/updater validation/recovery boundaries first.
- Do not claim conclusions from overnight REA output until reviewed.

#### Unresolved
- Overnight REA package being prepared/executed separately; output not yet reviewed.
- Exact user-unit screen-controller revision unconfirmed.
- Interrupted-write recovery behavior UNKNOWN.
- Image-level self-checksum UNKNOWN.
- Next task: Review overnight REA output, map conclusions to reproducible evidence, decide if evidence sufficient for non-flashing screen-runtime prototype; do not proceed to custom flashing solely from inferred image structure.

#### Cross-references
- Detailed 2026-11-20 entries (E52-E54, cap4/cap5, LT168 manual pages, UI format findings, teardown photos) appear later in this Unreleased section.

### AULA L99 research checkpoint (2026-11-18)

#### Confirmed
- REA host `rea` (10.1.0.107) reachable via `plink.exe -batch -i $env:USERPROFILE\.ssh\aula-rea.ppk reauser@10.1.0.107 "hostname"` → `rea`.
- V4 full-firmware pipeline: PIPELINE_COMPLETED; 19463 functions attempted, 19460 decompiled, 3 failed; RUNTIME_LCD_UNVERIFIED.
- SerialPortTool Targeted Deep V1: COMPLETED (34 jobs, 0 failures); targets 0x408c10, 0x407ad0, 0x407dc0, 0x407ef0, 0x408250, 0x4087e0; Verdict: TARGETED_EVIDENCE_COLLECTED.
- P21_FINAL_ACCEPTANCE.md: Page 21 Mini Numpad descriptor schema VERIFIED_STATIC; 19-byte record layout; numpad_1 at header offset 0x00024CA9, payload offset 0x00024CAC; unpressed=341 (0x0155), pressed=342 (0x0156), goto=0xFFFF.

#### Strongly supported
- HFD Code V2.3 little-endian M*Core architecture fingerprint based on structural and third-party implementation evidence (not Levetop vendor-confirmed).
- Candidate image base 0x60010000; 21 candidate entries verified in-range, 2-byte aligned, within image.
- Canonical M*Core CFG checkpoints: 4096 baseline, 8192/512, 8192/1024, 12288/1024, 12288/1536 (PASS_BUDGET_TRUNCATED, reconciliation PASS).
- JMPI evidence: literal-pool helper ACCEPTED; standalone post-processor ACCEPTED; legacy integrated JMPI mode RETIRED.

#### Locally correlated candidate (not confirmed on user unit)
- DeviceDriver.exe static analysis (HM3): GetPrivateProfileStringW reads CPU_Temperature/GPU_Temperature from `C:\Program Files (x86)\AULA L99\data.ini` (canonical telemetry path); HID via WriteFile/DeviceIoControl; no HidD_SetFeature/GetFeature.
- HM4B: WriteFile callsite 0x004707AA (FUN_00470670, may contain XOR); DeviceIoControl callsite 0x0045EE87 IOCTL 0xB0192 (FUN_0045ee50); USB G3 Type C begins `00 01 5A 1A`, ends `AA 55`.
- Safe Flash Blockers V1 / Owner and Marker V1 verdicts: SAFE_FLASH_NOT_READY; MARKER_XREF 60026e60 -> 6000f000 type=DATA owner=NONE.

#### Unverified
- Type 3 runtime mapping and dispatcher.
- Icon-selection formula.
- Native Type 3 runtime mapping.
- Runtime LCD update / dynamic Stream Deck.
- Host-facing input/parser/dispatcher → 0x600315D0 firmware-side edge.
- HardwareMonitor INI-to-HID complete dataflow.
- Image-level self-checksum in UartTFT-II_Flash.bin (UNKNOWN).
- Exact UI-only package acceptance (STRONG_INFERENCE only).
- Interrupted-write recovery behavior (UNKNOWN).

#### Safety decision
- Hardware flashing: NO-GO. Safe Flash Blockers V1 and Owner and Marker V1 both verdict SAFE_FLASH_NOT_READY. No hardware write is permitted until image-level self-checksum, write scope, interrupted-write recovery, and exact UI-only package acceptance are VERIFIED.

### AFRE Wave 2 research checkpoint (2026-11-16)

#### Added
- Real Ghidra 12.1.4 extraction completed against canonical firmware `HFD_Code_V2.3.bin` — 313,652 bytes, SHA-256 `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03`
- Full extractor determinism reported PASS
- Real coverage accounting completed:
  - firmware_bytes: 313,652; mapped_bytes: 313,652 (100% mapped coverage)
  - instruction_bytes: 72,070 (22.98% instruction-byte density); defined_data_bytes: 8,817; undefined_bytes: 232,765
  - overlap_bytes: 0
  - function_owned_instruction_bytes: 34,764 (48.24%); unowned_instruction_bytes: 37,306
- Page 21 schema verification VERIFIED: 17 touch records, 19-byte descriptor schema, return codes 0x0030–0x0040, normal and pressed icon IDs verified
- Corrected resource offsets VERIFIED: NumPad 1 header offset 0x00024CA9, payload offset 0x00024CAC; old offset 0x00024A81 contradicted
- USB HID findings VERIFIED: Numpad 1 usage 0x59, Numpad 2 usage 0x5A, Numpad 3 usage 0x5B

#### Research status
- Wave 1: Accepted research artifacts
- Wave 2: Real Ghidra extraction completed
- SQLite reconciliation integration: PARTIAL

#### Limitations
- Companion PARTIAL: Numpad 1 physical E2E verified at bridge layer only; Physical Companion E2E remains UNVERIFIED
- HardwareMonitor PARTIAL: .NET INI writer VERIFIED; DeviceDriver INI reader VERIFIED; INI-to-HID complete dataflow UNRESOLVED
- LCD Runtime research UNVERIFIED: Generic runtime icon update UNVERIFIED; Host-controlled widget update UNVERIFIED; Dynamic Stream Deck NOT COMPLETED
- Static Stream Deck MVP NOT claimed as complete.

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

### AULA L99 V9.2 validated collector checkpoint (2026-11-16)

#### Added
- Validated V9.2 Session A computed-call collector: `V92ComputedCallCollector.java` — status FIX_A_PASS; final SHA-256 `5F8E9E244F563AF18A243388E1BD50AD87EF3B65591BAD9C7B7B9F54A24835BF`; live output 43776 bytes, SHA-256 `346b3d103808b7ea5fc72f7d191182002221de4061433b4e640597e5c01b4239`
- Validated V9.2 Session B shared-state collector: `V92SharedStateCollector.java` — status FIX_B_PASS_ON_DISPOSABLE_PROJECT (superseding FIX_B_PROJECT_INTEGRITY_FAILED); final SHA-256 `F256C3593C45F3684CB49DE506BC64C29F57EE37C5E39C4707AB1D391BEF22C6`; live output 329455 bytes, SHA-256 `7a0410ee4189f28105ec4bd12776ae61140d1ea5c69e6576c0dbf01391e97eb2`
- Validated V9.2 Session C boundary collector: `V92BoundaryCollector.java` — status FIX_C_PASS; final SHA-256 `56745F0A0B5898D549DBCDAE6A812F1778817A4208596AD8D8D19B785EF0A17E`; live output 280864 bytes at target `0x60049B90`; classification INSUFFICIENT_EVIDENCE
- Real Ghidra 12.1.4 compile and execution validation passed for all collectors
- Disposable-project isolation introduced after the B integrity incident
- Checkpoint `d42f6f1` pushed to `main`; local HEAD and origin/main matched
- Current research verdict: INSUFFICIENT_EVIDENCE
- Runtime package rebuild still required before pipeline acceptance

#### Verification
- local HEAD and origin/main matched at d42f6f1

### Safe dynamic COM port discovery for EEEF:268A (2026-11-16)

#### Added
- New Windows COM discovery module: `src/aula_bridge/windows_com_discovery.py`
  - PowerShell Get-CimInstance against Win32_PnPEntity with -NoProfile -NonInteractive
  - Machine-readable JSON output parsed defensively
  - Subprocess argument arrays (no shell=True)
  - Bounded timeout (default 10s)
  - Dependency injection for offline testing
- Dynamic COM port discovery integrated into `scripts/replay_captured_screen_win32.py`
  - Automatic discovery when --port omitted
  - Explicit --port always wins (bypasses discovery)
  - --detect-port mode: prints resolved COM port, exits without loading payload or opening port
  - --detect-port and --port together rejected by argparse
  - Removed hard-coded COM8 implicit fallback
- Fail-closed discovery behavior:
  - Zero EEEF:268A devices → NoMatchingDeviceError with actionable message
  - Multiple EEEF:268A COM ports → MultipleMatchingDevicesError listing candidates
  - Duplicate inventory records for same COM port deduplicated
  - Keyboard HID VID:PID 0C45:800A explicitly ignored
  - Unrelated USB serial devices ignored
  - Matching records without valid COM port ignored
  - Malformed records handled gracefully
  - Case-insensitive VID:PID matching
  - COM port validation: COM1-COM999 only, normalized to uppercase
- 44 focused offline tests added: `tests/test_windows_com_discovery.py`
  - Discovery parsing and selection (13 cases)
  - Inventory acquisition (8 cases)
  - CLI behavior (4 cases)
  - No hardware access verification (3 cases)
- All 38 existing Win32 transport tests continue to pass

#### Changed
- README.md: Documented automatic discovery, --detect-port, explicit --port override
- Removed PORT_DEFAULT = "COM8" from replay_captured_screen_win32.py

#### Safety
- No COM port opened during discovery or tests
- No serial/USB/HID operations
- No physical device accessed
- No payload sent during discovery or --detect-port
- All tests fully offline with mocked inventory

#### Verification
- `python -m pytest tests/test_windows_com_discovery.py tests/test_win32_transport.py -v` → 82 passed
- aula_payload_hex.txt SHA-256 unchanged: 1e3e6356ad0be3c1b0a6745c74bf0dccfe33bce35eb1537bf81e6eeca2ada673
- Payload: 154 chunks, 309,071 bytes (unchanged)

### End-of-day documentation consolidation (2026-11-15)

#### Physical Raw Input (VERIFIED)
- Keyboard identity: VID 0C45, PID 800A, Raw Input interface MI_00.
- MI_01&Col03 observed but NOT the verified Mini Numpad keyboard-input path.
- Mini Numpad 1: make_code 79/0x4F, vkey 97/0x61, key down then key up, is_repeat false, reproduced multiple times.
- Device-selection defect: find_target_device previously selected first device matching only VID/PID; both MI_00 and MI_01&Col03 expose 0C45:800A, so enumeration order could select MI_01&Col03. Updated so AULA L99 0C45:800A uses MI_00. Focused device-selection tests passed.

#### Bridge runtime diagnostics (REJECTED / superseded)
- Earlier claim "normal mode never receives WM_INPUT" is REJECTED / superseded.
- Latest normal-mode diagnostics prove normal mode: RegisterClassW, CreateWindowExW, non-zero HWND, RAWINPUTDEVICE (usage_page 0x01, usage 0x06, flags 0x100), RegisterRawInputDevices, message loop, WM_INPUT, process_raw_input, resolves RIDI_DEVICENAME as VID_0C45&PID_800A&MI_00, matches MI_00, matches 0C45:800A.
- Latest sample reached a key mapping decision for vkey 0x11 / make_code 0x1D (not Mini Numpad 1).
- Final physical production path NOT yet verified. Controlled one-key test pending (Mini Numpad 1 → vkey 0x61 / make_code 0x4F → numpad_1 → short_press → one Companion HTTP 200).

#### Companion v5.1.3 (VERIFIED offline)
- Bitfocus Companion v5.1.3, binding 127.0.0.1:8000, harmless AULA TEST button at UI location 1/1/1.
- Prepared mapping: numpad_1, page 1, row 0, column 0.
- Verified endpoint: POST http://127.0.0.1:8000/api/location/1/0/0/press returns HTTP 200 via manual PowerShell POST.
- CompanionDispatchWorker: bounded capacity 8, hold suppressed, secondary_hold suppressed, queue overflow protection works. Previous queue_size test failure was a test timing/expectation defect; production worker did not require a queue-size logic fix.
- Physical Companion E2E still UNVERIFIED.

#### Page 21 UI (offline, ACCEPTED_WITH_LIMITATIONS)
- Offline 320x480 Stream Deck prototype, 17 action zones, return codes 0x0030–0x0040.
- Home/Back: return_code 0x0020, goto_page 1. Home rectangle coordinates UNKNOWN; 17 action zones not physically proven non-overlapping with Home.

#### RGB565 export (VERIFIED, RGB565_EXPORT_ACCEPTED)
- 320x480, 307200 bytes raw RGB565. SHA256: 524b0dcd866d1554586e599b9767e06f6e8ab56eff728baae43e17684c58d304.
- Determinism PASS (two independent in-memory conversions identical). Max per-channel error 7, mean 2.9973. 7 focused tests passed.
- Proves deterministic offline framebuffer conversion only; NOT firmware resource compatibility, ARGB4444 replacement safety, runtime LCD framebuffer control, flash-update checksum correctness, or safe physical LCD deployment.

#### Win32 Photo Frame transport (READY_FOR_CONTROLLED_PHYSICAL_TEST)
- Corrections: partial-write continuation, zero-byte write rejection, targeted CancelIoEx cancellation, completion drain, pending-read cleanup, native-buffer lifetime handling, duplicate-write prevention.
- 38 focused transport tests passed through injected Win32 API boundary.
- Software-side readiness only; physical throughput UNVERIFIED. Future physical test must dynamically resolve EEEF:268A COM port (no hard-coded COM3/COM8).
- Custom white Photo Frame image previously displayed via slower custom upload path = verified Photo Frame upload capability, NOT runtime framebuffer control.

#### USB attribution (corrected)
- Keyboard 0C45:800A; Screen EEEF:268A. Validated capture correctly attributed LCD screen device and separated from unrelated Realtek bulk traffic.
- Normal Mini Numpad and Photo Frame navigation did NOT expose verified screen-CDC runtime-control stream.
- Third-party Levetop evidence magic 5A A5 / write opcode 0x10 is THIRD-PARTY REFERENCE ONLY, unverified on user-unit traffic.

#### Ubuntu REA
- Remote reauser@10.1.0.107, host rea, root /home/reauser/rea-lab, Ghidra 12.1.4, OpenJDK 21, MCORE:LE:32:default.
- Firmware /home/reauser/rea-lab/transfer/HFD_Code_V2.3.bin, 313652 bytes, SHA-256 a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03.
- Bulk firmware extraction must be deterministic and run directly on Ubuntu REA VM; Coding Agents for bounded interpretation/implementation/tests/docs only.

#### Full Firmware RE V1–V6
- V1: SUCCESS/PASS, ~73s, 1 function, 242 call graph rows, 760 external memory references, canonical edge oracle PASS. Default raw-binary Ghidra discovery insufficient.
- V2: SUCCESS/PASS, ~90s, 4 recovery rounds, 190 seeds discovered, 183 attempted, 107 functions.
- V3: SUCCESS/PASS, ~94s, 7 rounds, 193 seeds, ~118 functions, 33224 decoded bytes, 0.105926 decoded fraction, 118 decompile success / 0 failed. call_graph.csv zero useful edges; call-graph extraction defect exposed.
- V4: AUDIT_COMPLETE_WITH_LIMITATIONS / PASS. 118 functions, 193 seeds, 0 call graph rows, 769 memory refs, 8002 function-body covered bytes, 103 gaps, 76 seed non-function outcomes. Gaps not proven code gaps.
- V5: SUCCESS/PASS. Canonical raw-byte edge evidence valid; 0 new literal-call candidates; 76 unresolved seed rows; logs insufficient for proper MCore call graph.
- V6 Combined: SUCCESS/PASS, ~94s, 193 seeds, 193 attempted, 8 rounds, 117 functions, 33224 decoded bytes, 584 call edges, 0 unresolved calls, 770 memory refs, 118 decompile success / 0 failed. Call-graph extraction layer repaired. Canonical edge 0x600315D0 → 0x60049D98 (jsri 0x60031620, literal pool 0x60031620, LITERAL_BACKED_JSRI, STRONG_INFERENCE) confirmed in call_graph.csv and oracle.json. Downstream calls from 0x60049D98 toward 0x60036D04, 0x600414A0, 0x60049E50, 0x60049B90, 0x60047778. 0x600315D0 has zero recovered incoming call edges; no host-facing parser/dispatcher upstream. DISPLAY_PATH_ONLY.

#### Corrections / rejected hypotheses (REJECTED)
- 0x81D000 as confirmed framebuffer address.
- 0x81BCxx as confirmed LCD MMIO.
- 0x81E36D as confirmed display address.
- 0x800897 / 0x800898 / 0x800899 as confirmed display addresses.
- 0x60031620/24/28/30 as four caller functions (they are literal-pool DATA).
- Batch 4 four-target display path.
- Photo Frame upload as runtime framebuffer control.
- Third-party 5A A5 / opcode 0x10 as verified user-unit traffic.
- Normal Bridge never receiving WM_INPUT.

#### Process / token lessons
- Bulk firmware extraction → Ubuntu REA scripts; Coding Agent → bounded implementation/review/tests/docs (~10K–20K tokens).
- Preserve per-edge evidence: source VA, raw instruction, literal-pool VA, resolved target, edge type, confidence.
- Literal-pool data is not a function. Scan-window address is not a true call instruction source. Pipeline PASS does not verify a hypothesis. Negative evidence is valid.

#### Remaining blockers
- Companion: final one-key physical E2E test (Mini Numpad 1 → vkey 0x61 → make_code 0x4F → numpad_1 → short_press → one HTTP 200).
- LCD UI: safe deployment method, resource-format compatibility, ARGB4444 safety, checksum handling, runtime LCD write path.
- Win32 Photo Frame: controlled physical speed/robustness test vs dynamically enumerated EEEF:268A COM port.
- Firmware RE: host-facing input path into 0x600315D0 missing; V7 next.

#### Next planned task
- Full Firmware RE V7 (Indirect Entry / Address-Taken / Pointer-Table Audit) on Ubuntu REA, starting from V6 artifacts.

### Full Firmware RE V7/V7.1 (2026-11-16)

#### Initial V7 execution (SUCCESS/PASS; audit trail, partially superseded)
- Full Firmware RE V7 executed on Ubuntu REA starting from V6 artifacts.
- Execution: SUCCESS. Pipeline acceptance: PASS.
- Target: 0x600315D0.
- Aligned LE32 pointer hits to 0x600315D0: 0.
- Contiguous pointer-table candidates containing 0x600315D0: 0.
- Direct incoming V6 edges to 0x600315D0: 0.
- Initial reported zero-incoming roots: 584; recovered function inventory: 0 — SUPERSEDED by V7.1, not accepted as research results.
- Root cause of the accounting issue: graph calculation used source_instruction instead of source_function; V6 functions.csv was not loaded successfully; call-site instruction addresses were incorrectly treated as graph-source nodes. The reported 584 roots closely reflected the V6 call-edge count rather than a valid recovered-function root count.
- Initial V7 is not recorded as a total failure: no aligned LE32 pointer, no contiguous pointer-table candidate, and no direct incoming V6 edge to 0x600315D0 were found, and these negative findings remain valid.

#### Corrected V7.1 result (current accepted firmware-analysis checkpoint)
- Full Firmware RE V7.1: Execution SUCCESS, Pipeline acceptance PASS, JSON validation PASS.
- Target: 0x600315D0.
- Recovered function inventory: 118.
- Zero-incoming recovered-function roots: 42.
- Unresolved source sites: 368.
- Evidence-backed non-function seed candidates: 390.
- Aligned LE32 pointer hits to 0x600315D0: 0.
- Contiguous pointer-table candidates containing 0x600315D0: 0.
- Direct incoming V6 edges to 0x600315D0: 0.
- V7.1 corrected the accounting by: using source_function for function-level graph construction; retaining source_instruction as instruction-site evidence; explicitly loading V6 functions.csv; recognizing the function inventory columns function_va, end_exclusive, body_bytes; separating rows with blank source_function into unresolved source sites; separating recovered-function roots from non-function seed candidates.

#### Accepted research conclusion
- No aligned absolute little-endian 32-bit pointer or contiguous pointer-table evidence was found for indirect entry into 0x600315D0.
- Execution verdict: SUCCESS / PASS.
- Bounded target-pointer verdict: NO_ALIGNED_ABSOLUTE_POINTER_EVIDENCE.
- Overall target-entry conclusion: INDIRECT_ENTRY_NOT_ESTABLISHED.
- Negative evidence is valid only within the tested scope. A raw pointer is not a call; a pointer-table candidate is not runtime reachability.
- V7.1 did not eliminate: unaligned pointers, relative pointers or offsets, encoded pointers, split-immediate address construction, runtime-populated RAM dispatch tables, computed branch targets, interrupt or callback entry, branch or fall-through reachability, and state-machine dispatch that does not materialize the complete absolute address.
- Pipeline PASS is not proof of the complete research hypothesis.

#### Evidence limitations
- 42 zero-incoming recovered-function roots are static investigation candidates, not 42 proven runtime entry points. They may include image entry points, interrupt handlers, callback handlers, indirectly reached functions, and roots caused by incomplete recovery.
- 368 unresolved source sites are evidence-backed call-edge source instructions for which V6 did not recover a source_function attribution. They are not automatically separate functions.
- 390 evidence-backed non-function seed candidates are conservative candidates derived from unresolved source sites and graph targets absent from the recovered function inventory. They are not confirmed functions, callers, missing functions, or code regions.

#### Canonical V6 evidence preserved
- source instruction 0x600315D0, source function 0x600315D0, raw word 0x7F14, instruction jsri 0x60031620, literal pool 0x60031620, resolved target 0x60049D98, edge type LITERAL_BACKED_JSRI, confidence STRONG_INFERENCE.
- 0x600315D0 has zero recovered direct incoming V6 call edges. No USB, CDC, HID, UART, packet-parser, or other host-facing node has been connected upstream to 0x600315D0. The exact missing firmware-side edge remains: host-facing input/parser/dispatcher -> 0x600315D0. Confirmed firmware evidence remains display-path evidence only; the host-facing upstream remains unknown.

#### Next bounded phase (proposed, not executed)
- Full Firmware RE V7.2: Target-Proximity and Root-Triage Audit — proposed scope triages the 42 zero-incoming roots, the 368 unresolved source sites, bounded branch-span and fall-through evidence around 0x600315D0, and whether 0x600315D0 lies inside another recovered function range.
- V7.1 is complete. V1 through V7.1 do not need to be rerun. V7.2 is proposed but has not been executed. V8 direction remains undecided pending bounded V7.2 evidence.

#### Confirmation
- No firmware flashing or screen write was performed. Firmware work remains read-only.

### Session A evidence consolidation (2026-11-15)

#### ADDED
- Raw Input: RID_DEVICE_INFO union defect identified; VID/PID parsed from RIDI_DEVICENAME; physical AULA L99 attribution verified (VID 0C45, PID 800A, MI_00); NumPad 1 and Home/Back physically verified; 41 focused tests passed.
- Companion: WidgetDispatchAdapter hold and secondary_hold suppression fixed; 74 focused tests passed; live-test configuration prepared; live HTTP end-to-end test NOT performed.
- Page 21 UI: offline 320x480 Stream Deck prototype generated; 17 logical zones mapped to 0x0030–0x0040; Home navigation record preserved; exact Home rectangle unverified; physical LCD deployment blocked.
- Win32 transport: partial-write continuation implemented; zero-byte write rejected; CancelIoEx cancellation and completion drain added; 38 focused tests passed; physical speed test NOT performed.
- USB capture: EEEF:268A attributed to USB bus 2, device 13 in validated captures; Mini Numpad and Photo Frame navigation produced no observed screen CDC runtime traffic; unrelated Realtek bulk traffic not attributed to the LCD.
- Ubuntu REA: HFD_Code_V2.3.bin verified (313652 bytes, SHA-256 a76806ad...); Batch 1 SUCCESS/PASS/INCONCLUSIVE; Batch 2 SUCCESS/PASS/PARTIAL_CHAIN; Batch 3 DISPLAY STRONG_INFERENCE at 0x60049D98, MEMORY_HELPER VERIFIED at 0x60049B90 and 0x60047778, 0x600315D0→0x60049D98 NOT CONFIRMED; Batch 4 reached acceptance but FAILED, DISPATCHER_TO_DISPLAY_PATH NOT ACCEPTED, manifest not generated, verdict INCONCLUSIVE pending artifact audit.

#### REJECTED CLAIMS (do not record as verified)
- Batch 4 DISPATCHER_TO_DISPLAY_PATH.
- 0x600315D0 → 0x60049D98 path.
- 0x81D000 and 0x81BCxx as confirmed display addresses.
- Photo Frame upload as runtime framebuffer control.

#### BLOCKERS
- Live Companion HTTP end-to-end test not performed; exact Page 21 Home rectangle unverified; physical LCD deployment blocked; Win32 physical speed test not performed; Batch 4 artifact audit pending.

#### NEXT PLANNED TASKS
1. Audit Batch 4 false path attribution.
2. Controlled Mini Numpad to Companion live test.
3. Controlled EEEF:268A Win32 physical speed test.
4. Resolve safe LCD deployment for the Page 21 UI prototype.

### Companion Windows Bridge opt-in integration (final companion bridge documentation)

#### ADDED
- Companion opt-in configuration loader (`src/aula_bridge/companion_optin_config.py`): strict JSON validation, loopback-only host, port/timeout checks, disabled-by-default behavior.
- Bounded Companion dispatch worker (`src/aula_bridge/companion_dispatch_worker.py`): one daemon thread, FIFO queue capacity 8, non-blocking admission, overflow and shutdown-drop accounting, bounded join.
- CLI + JSON dual-gate integration in `aula_input_bridge.py` (`--enable-companion`, `--companion-config`).
- Worker and configuration tests, runtime integration tests, startup failure injection tests, and runtime observability tests.

#### CHANGED
- Windows Bridge optional transport selection: Companion is opt-in; the default path still uses `MockTransport`.
- Non-blocking Companion dispatch: HTTP I/O runs on the dedicated Worker thread, not on the Windows Raw Input message loop.
- Startup and shutdown cleanup: message loop wrapped in `try/finally`; deterministic `dispatcher.close()` then `provider.close()` ordering.
- Worker shutdown race protection: `send()` and `close()` serialize admission and draining under a lock.
- Startup Worker leak repair: dispatcher initialization failure closes the Worker; no partial Worker is left running.

#### VERIFIED
- Default-disabled behavior: missing config or `enabled=false` does not enable Companion.
- Strict config and mapping validation: duplicate keys, unknown fields, wrong types, and invalid ranges rejected.
- Worker FIFO ordering preserved.
- Overflow and shutdown-drop accounting are independent and observable.
- Device and sequence preservation: `ProviderEvent.device` and `seq` preserved; Worker snapshots events with `dataclasses.replace()`.
- Short-press-only HTTP behavior: `hold` and `secondary_hold` produce zero HTTP requests.
- Offline regression results: `python -m pytest tests -q --basetemp=C:/temp/aula-l99-pytest-validation` → 1102 passed, 67 subtests passed, exit code 0.

#### LIMITATIONS
- No live Companion acceptance: live Companion behavior has not been independently validated.
- No production deployment approval.
- In-flight HTTP cannot be forcibly cancelled; shutdown uses a bounded join and logs if the worker remains alive.
- Firmware/LCD research remains separate; no firmware, CFG, GT911, or LCD runtime-control changes.

### Offline research checkpoints documentation sync

#### Added
- Synchronized README.md, CHANGELOG.md, and docs/PROJECT_HANDOVER.md with five accepted offline research checkpoints (documentation only; no source/firmware changes).

#### Accepted checkpoints
1. **Address Xref Scanner** (`scripts/research/hfd_address_xrefs.py`, `tests/test_hfd_address_xrefs.py`) — **ACCEPT_WITH_LIMITATIONS**
   - Bounded deterministic offline byte-pattern scanner for target address 0x0086EF40 in HFD_Code_V2.3.bin
   - Raw byte-pattern matches + bounded local instruction-context inspection (immediate 2-byte word)
   - Does NOT perform recursive disassembly, CFG traversal, or instruction validation
   - Prohibited range 0x60031198-0x600315D0 flagged
   - Firmware verification (size 313652, SHA-256 A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03)

2. **Offline Runtime Frame Codec** (`scripts/research/l99_runtime_frame_codec.py`, `tests/test_l99_runtime_frame_codec.py`) — **ACCEPT**
   - Deterministic offline encoder/decoder for AULA L99 short runtime USB protocol
   - Frame format: 5A A5 | length:u8 | body | CRC16:LE16
   - Read opcode 0x03 (word_address:BE16, word_count:BE16, max 8)
   - Write opcode 0x10 (word_address:BE16, word_0:BE16...)
   - Address range 0x0000–0xFFFF, CRC16/MODBUS (poly 0xA001, init 0xFFFF)
   - Full round-trip tests and error-case coverage; no hardware access

3. **Capture Frame Classifier** (`scripts/research/l99_capture_frame_classifier.py`, `tests/test_l99_capture_frame_classifier.py`) — **ACCEPT_WITH_LIMITATIONS**
   - Deterministic offline classifier for existing USB capture CSV exports
   - Frame classes: VALID_RUNTIME, INVALID_RUNTIME, UNVERIFIED_LARGE_PAYLOAD, UNKNOWN, CRC_VALID_UNSUPPORTED_OPCODE
   - Endpoint attribution via capture-local device mapping (aula_home_numpad_transition.pcapng)
   - Bounded memory, no hardware access, device addresses capture-local only

4. **USB Device Attribution Utility** (`scripts/research/l99_usb_device_attribution.py`, `tests/test_l99_usb_device_attribution.py`) — **ACCEPT_WITH_LIMITATIONS**
   - Extracts capture-local USB device address → VID/PID mappings from pcapng via tshark
   - Verifies capture SHA-256 (B4DAD6E13612C615F3A03400BCC9EED8F98F6D02E0B256368B8E82C3C608F5EE)
   - Targets device addresses 6, 13, 15, 16; preserves capture-local addresses
   - Requires tshark; no live USB access; output is capture-specific

5. **Screen-Control Evidence Inventory** (`docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md`) — **ACCEPTED**
   - Consolidated inventory of USB-only screen-control evidence from accepted checkpoints
   - Verified interfaces, upload behavior, runtime protocol (Levetop ref only), touch transport
   - Display-update limitations (no live framebuffer verified), page-switch status, GT911 status
   - Hardware NO-GO with critical blockers; open questions; next milestone evidence recommendations

#### Important
- **Screen Capture Evidence Utility** (`scripts/research/l99_screen_capture_evidence.py`, `tests/test_l99_screen_capture_evidence.py`) — **REVIEW_PENDING**
  - Do NOT mark as ACCEPTED; review pending

#### Verified
- Repository state at sync: HEAD `13b1ff06d99c837a1c2690ae897f84d27a51db66`, branch `main`, working tree clean for tracked files
- New files staged: `docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md`, `scripts/research/hfd_address_xrefs.py`, `scripts/research/l99_runtime_frame_codec.py`, `scripts/research/l99_capture_frame_classifier.py`, `scripts/research/l99_usb_device_attribution.py`, test files
- Untracked analysis scripts and outputs present (not staged)
- `python -m pytest tests -q` passes for repo test suite

#### Preserved constraints
- Verified firmware identity: HFD_Code_V2.3.bin 313652 bytes SHA-256 A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03
- Canonical CFG checkpoints: 4096 baseline, 8192/512, 8192/1024, 12288/1024, 12288/1536 (PASS_BUDGET_TRUNCATED, reconciliation PASS)
- JMPI evidence: literal-pool helper ACCEPTED, standalone post-processor ACCEPTED, legacy mode RETIRED
- Hardware flashing: NO-GO
- Runtime LCD update: UNKNOWN
- GT911: HOLD (public teardown only)
- Opcode 0x64 NOT claimed as verified screen-control command
- 2060-byte packets NOT claimed as proof of live framebuffer refresh
- No research tools altered; no commits/tags/pushes/version bump

### Companion offline integration (documentation sync)

#### Added
- Synchronized README.md, CHANGELOG.md, and docs/PROJECT_HANDOVER.md with the Companion offline integration audit (documentation only; no source/firmware changes).
- New untracked companion modules: `src/aula_bridge/companion_button_mapping.py`, `src/aula_bridge/companion_dispatch_adapter.py`, `src/aula_bridge/companion_http_transport.py`, `src/aula_bridge/companion_http_sender.py`, `src/aula_bridge/companion_transport.py`, `src/aula_bridge/companion_types.py`.
- New untracked test files: `tests/test_companion_button_mapping.py`, `tests/test_companion_dispatch_adapter.py`, `tests/test_companion_dispatcher_integration.py`, `tests/test_companion_http_transport.py`, `tests/test_companion_http_sender.py`, `tests/test_companion_offline_e2e.py`, `tests/test_mock_companion_transport.py`.

#### Verified safety properties
- Short-press-only behavior: only `short_press` events processed; hold/secondary_hold/key_down/key_up/repeat_ignored ignored (zero HTTP requests).
- Hold and secondary_hold suppression: all hold-type events produce zero HTTP requests.
- Device identity preservation: `ProviderEvent.device` never mutated; logged in INFO logs; included in transport metadata.
- Event sequence preservation: `ProviderEvent.seq` never mutated; dispatch order preserved through mock transport.
- HTTP response logging: key, device, seq, event, status_code, success, error_code logged; status codes mapped to semantic error codes.
- HTTP failure handling: all non-200 responses produce `HttpResponse(success=False)`; no exceptions propagate.
- No default button mappings: explicit mapping file required; no automatic locations invented.
- Strict JSON validation: duplicate keys rejected; version must be integer (version 1 only); location fields must be genuine integers; negative values rejected; unknown keys rejected; extra fields rejected; missing required fields rejected.
- No automatic retries: exactly one sender call per press; redirects rejected.
- No event buffering: each `send()` processes exactly one event; `flush()`/`close()` are no-ops.
- No background threads: all calls synchronous; no threading/asyncio/concurrent.futures.
- No accidental live network activation: all tests use fake/mock senders; loopback-only validation; `http://` scheme only.
- No firmware/hardware access: zero imports of serial/usb/hid; pure Python; dependency injection.
- No modification of accepted Bridge behavior: ActionDispatcher, ProviderEvent, DryRunProvider unchanged.
- HTTP sender security: redirect rejection, scheme validation (http:// only), userinfo rejection, path/query/fragment restriction, loopback-only restriction — all verified.

#### Remaining risks (not resolved)
- No integration test with real Companion instance (UNKNOWN — all tests use fakes).
- Button mapping file not hot-reloadable (INFERENCE — loaded once at startup).
- No authentication support (INFERENCE — Companion may require auth token).
- Single-threaded synchronous HTTP (INFERENCE — blocking I/O; timeout mitigates).
- No health check / connection verification (INFERENCE — no pre-flight reachability check).
- Error codes not mapped to user actions (INFERENCE — logs errors but no retry/backoff/alerting).
- No encryption (HTTP only) (VERIFIED — http:// only; loopback mitigates).
- Fixed 5s default timeout (INFERENCE).
- No circuit breaker (INFERENCE — repeated failures don't pause dispatch).

#### Acceptance recommendation
- **ACCEPT** — Companion integration is safe for offline development and testing.
- Not yet suitable for production deployment with live Companion.

#### Verified
- Repository state at sync: HEAD `65d071981ddc132758cf0dd4d11ad34735990856`, branch `main`, working tree clean for tracked files (untracked companion modules present).
- `python -m pytest tests -q` passes for repo test suite (797 passed, 47 subtests passed).
- `git diff --check` clean.

### JMPI evidence research checkpoint (documentation sync)

#### Added
- Synchronized README, CHANGELOG, and PROJECT_HANDOVER with the accepted JMPI evidence research checkpoint (documentation only; no source/firmware changes).
- Recorded accepted implementation commits:
  - `89ca1201ec8ff94497df7d8be68f260b9ff87b58` — `research: add validated MCore literal pool helper` (`scripts/research/mcore_literal_pool.py`, `tests/test_mcore_literal_pool.py`).
  - `8b0b47a51db719721d36bb029de4a4dec7011fd6` — `research: add deterministic JMPI evidence postprocessor` (`scripts/research/jmpi_evidence_postprocess.py`, `tests/test_jmpi_evidence_postprocess.py`).
- Recorded deterministic JMPI literal-pool evidence artifact: `local_analysis/cfg_experiments/jmpi_evidence_postprocess/jmpi_literal_pool_evidence.json`, SHA-256 `B4D4D323E8B948F1D87D6DB008A016049B6C2D728CA78B595A2D14DC903C1AA3` (verified against artifact).
- Recorded ROM jump-table research findings (static evidence): indirect jump site `0x6004D68A`, ROM table base `0x60016458`, 11 candidate entries (index 0–10), common join `0x6004D742`; all 11 cases write a 32-bit constant to `0x0086EF40`; default path writes `0x0001C200`. ISA semantics remain decoder-dependent.
- Recorded cleanup: legacy traversal-integrated JMPI implementation retired; backup patch `C:\temp\aula-l99-jmpi-legacy-backup.patch` SHA-256 `01CA8DD905211502A77FC4620B1BDEF411253AFB9FDB6E01E31F427BB08F659F`.

#### Verified
- Repository state at sync: HEAD `8b0b47a51db719721d36bb029de4a4dec7011fd6`, branch `main...origin/main [ahead 2]`, tracked working tree clean, `analyze_pending.py` untracked.
- `python -m pytest tests -q`: 356 passed in 12.74s (repo `tests/` suite). Full-root `pytest -q` reports collection errors in external `tools/Aula_L99_Linux-main/...` due to missing environment deps/module name collisions outside this repository’s test scope.
- Standalone JMPI evidence post-processor is independent of CFG traversal; `DEFAULT_BUDGETS` unchanged; no roots added; existing accepted CFG artifacts unchanged.
- JMPI evidence (artifact-derived): 52 unresolved indirect-flow sites total; 49 validated JMPI literal targets; 3 register-indirect sites preserved (record-level). 15 unique literal targets; 0 invalid literal targets. Deterministic post-processor output. Canonical membership (validated JMPI literal-target records): 23 `BLOCK_START`, 1 `INSIDE_BLOCK`, 25 `NON_CANONICAL`. Distinct record-level vs unique-target counts preserved.
- `0x0086EF40` cross-reference audit remains incomplete due to agent output-limit interruption; hardware register purpose not claimed.

#### Decision gates
- Literal-pool helper: ACCEPTED
- Standalone post-processor: ACCEPTED
- Legacy integrated JMPI mode: RETIRED
- CFG budget expansion: HOLD
- Resolved-edge integration: HOLD
- Type 3 investigation: HOLD
- Hardware flashing: NO-GO

#### Next research
- Bounded `0x0086EF40` cross-reference audit.
- Screen-control protocol research.
- Independent ISA verification when needed.

### Added (prior uncommitted notes)
- Added the constrained experimental single-root 8192 safety profile (`--experimental-single-root-8192`, profile name `experimental_single_root_8192`). Requires exactly one root `0x60017490`, `max_instructions=8192`, all other budgets at `DEFAULT_BUDGETS` defaults (including `max_basic_blocks=512`). Output isolated under `local_analysis/cfg_experiments/`. `DEFAULT_BUDGETS` unchanged.
- Ran an isolated 8192 experiment that reached `max_basic_blocks` first (binding budget). The experiment expanded canonical coverage: blocks 475→666, instructions 3371→5238, edges 605→869, unique reachable bytes 6742→10476, candidates 66→77, 11 new queued candidates (`0x600221C0`, `0x600225EC`, `0x600235EC`, `0x60027C7C`, `0x6002F6B0`, `0x6002FCA0`, `0x60032B28`, `0x60032DD0`, `0x60034B60`, `0x60034D54`, `0x6004C412`). Accepted functions unchanged at 22. Two runs produced deterministic graph-output hashes.
- Independent Ubuntu/Ghidra startup verification completed: verified startup literals, two direct-call targets (`0x600174B8→0x60045150`, `0x600174BA→0x600449B0`), self-loop `0x600174BC→0x600174BC`. Ghidra 12.1.4 with ghidra-mcore (commit `2f32468f`, `MCORE:LE:32:default`). Local `mcore_le.cspec` compatibility patch applied (not vendor-confirmed; ABI correctness UNKNOWN).
- Working-tree changes in `scripts/research/hfd_cfg.py` and `tests/test_hfd_cfg_partition.py` implement queue-accounting fixes (shared helper `build_queue_accounting`, reconciliation enforcement, budget-exhaustion reporting, deterministic queue-record schema, candidate-versus-queue metrics, comparison CLI). These fixes are present in the working tree but the 8192 experiment was executed before they were applied; its generated outputs contain the pre-fix invalid accounting.

### Corrected
- Identified invalid canonical queue/pending reporting in the 8192 experiment outputs caused by hardcoded zero fields in `build_canonical_summary` (`queue_final_status_counts={}`, `pending_block_work=[]`, `pending_block_count=0`, `pending_function_work=[]`, `pending_function_count=0`, `pending_total_work=[]`, `pending_total_count=0`, `processed_or_resolved_queue_records=0`) and non-persisted queue records. Reconciliation skipped validation when status counts were empty. Block-loop exhaustion incorrectly recorded `budget_max_instructions` even when `max_basic_blocks` was the actual exhausted budget.
- Clarify that the committed 4096 checkpoint (`3ec58fd` implementation, `0387967` documentation) remains authoritative. No defaults or roots changed. The 8192 experiment is structurally informative and deterministic in graph topology but accounting-invalid; not accepted as a new default candidate.

### Accounting repair — ACCEPTED (uncommitted)

Accounting repair commit: `59696c1cac8c597427374af176fef9e2ab6859bd` — `fix: reconcile bounded HFD CFG queue accounting`.

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

8192 bounded experiment:
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

Decision gates:
- Accounting repair: ACCEPTED
- 8192 bounded experiment: ACCEPTED
- Increase `max_basic_blocks`: HOLD
- Change `DEFAULT_BUDGETS`: HOLD
- Add vector roots: HOLD
- Multi-root expansion: HOLD
- Type 3 investigation: HOLD

### 12288/1024 bounded experiment — ACCEPTED (uncommitted)

Implementation commit: `d324b641742b16a18ba8f3c4e1de8f35c575138f` — `research: add bounded 12288-1024 HFD CFG experiment`.

Added:
- New experimental CLI profile `--experimental-single-root-12288-blocks-1024` (profile name `single_root_12288_blocks_1024`). Requires exactly one root `0x60017490`, `max_instructions=12288`, `max_basic_blocks=1024`, all other budgets at `DEFAULT_BUDGETS` defaults. Output isolated under `local_analysis/cfg_experiments/single_root_12288_blocks_1024_run1/` and `..._run2/`.
- `DEFAULT_BUDGETS` unchanged (`max_instructions` 4096, `max_basic_blocks` 512). Existing profiles unchanged.
- Generated comparison `local_analysis/cfg_experiments/comparison_8192_vs_12288.json` comparing 8192/1024 vs 12288/1024 via existing CLI (`--compare-baseline-json`, `--compare-experiment-json`, `--compare-output`).

Acceptance:
- Binding budget: `max_basic_blocks` (hit first).
- `bounded_graph_acceptance_status`: `PASS_BUDGET_TRUNCATED`.
- Canonical blocks: 917 -> 1297.
- Canonical instructions: 7132 -> 10016.
- Canonical edges: 1179 -> 1634.
- Accepted functions: 48 -> 52.
- Queue discoveries: 264 -> 343.
- Processed/resolved: 202 -> 253.
- Pending blocks: 2 -> 14. Pending functions: 57 -> 65. Pending total: 59 -> 79.
- Pending queue records: 62 -> 90.
- Queue reconciliation: 253 + 90 = 343.
- Prohibited-range access: 0.
- Canonical safety counters zero.
- Two deterministic runs; six matching artifact hashes (run1 == run2).

Next research:
- Read-only frontier analysis of 90 pending queue records representing 79 unique addresses.

Next:

### 12288/1536 diagnostic experiment — ACCEPTED (uncommitted)

Implementation commit: `9c1204152ad56987250b8d9ad1aaec19f1dedcd7` — `research: add bounded 12288-1536 HFD CFG diagnostic experiment`.

Added:
- New experimental CLI profile `--experimental-single-root-12288-blocks-1536` (profile name `single_root_12288_blocks_1536`). Requires exactly one root `0x60017490`, `max_instructions=12288`, `max_basic_blocks=1536`, all other budgets at `DEFAULT_BUDGETS` defaults. Output isolated under `local_analysis/cfg_experiments/single_root_12288_blocks_1536_run1/` and `..._run2/`.
- `DEFAULT_BUDGETS` unchanged (`max_instructions` 4096, `max_basic_blocks` 512). Existing profiles unchanged.
- Generated comparison `local_analysis/cfg_experiments/comparison_12288_1024_vs_12288_1536.json` comparing 12288/1024 vs 12288/1536 via existing CLI (`--compare-baseline-json`, `--compare-experiment-json`, `--compare-output`).

Acceptance:
- Binding budget: `max_instructions` (hit first).
- `bounded_graph_acceptance_status`: `PASS_BUDGET_TRUNCATED`.
- Canonical blocks: 1297 -> 1330.
- Canonical instructions: 10016 -> 10223.
- Canonical edges: 1634 -> 1671.
- Accepted functions: 52 -> 52.
- Queue discoveries: 343 -> 348.
- Processed/resolved: 253 -> 259.
- Pending blocks: 14 -> 9. Pending functions: 65 -> 66. Pending total: 79 -> 75.
- Pending queue records: 90 -> 89.
- Queue reconciliation: 259 + 89 = 348; 152 + 107 + 89 = 348.
- Pending block/function union = 75 unique pending items.
- Prohibited-range access: 0.
- Canonical safety counters zero.
- Two deterministic runs; six matching artifact hashes (run1 == run2).
- `cfg_summary.json` SHA-256 `9BBE30E2F10A2FB49A77C76D79E30DB75C872909B1EE637DCA07027CB26AF592`.
- `cfg_reproducibility.json` SHA-256 `36076C84057B21F9A62F2A827A01F99AC0E9F6C4476F58B84563E52BA97DB8B9`.
- Target and decoder identities unchanged (`A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03`, `B6A4B5CBF5E7470AC82A96D19161EC803F3400DC4F65F09B3AECDE74B2A3326A`).
- Self-loop `0x600174BC` -> `0x600174BC` retained.
- Unresolved canonical indirect-flow edges: 52 (50 unresolved indirect jumps, 2 unresolved indirect calls).

Next research:
- Read-only static classification of 52 canonical unresolved indirect-flow edges: 50 unresolved indirect jumps, 2 unresolved indirect calls.

Next:
- Decision gates: Change `DEFAULT_BUDGETS` HOLD, raise `max_basic_blocks` HOLD, add vector roots HOLD, multi-root expansion HOLD, Type 3 investigation HOLD, hardware flashing NO-GO.

### Next

## v0.6.3 - 2026-11-10

### Added
- Recorded Chinese AULA L99 version 1.0.1.4 as the analysis baseline: only available version known to expose both keyboard firmware upgrade and screen firmware upgrade as separate upgrade paths targeting different controllers; keyboard updater version and screen updater version are not one version sequence.
- Recorded installed baseline: C:\Program Files (x86)\AULA L99; baseline inventory C:\temp\L99_1.0.1.4_baseline.txt; 212 files inventoried.
- Recorded DeviceDriver.exe (1,837,056 bytes, SHA-256 DD9C934E2F6F1CC53AE4AFB5B412C3F696CD4D329A03DF28BD151DAB90B3E6B3); Process Monitor confirmed Explorer launched DeviceDriver.exe and DeviceDriver.exe launched both firmware tools.
- Recorded verified keyboard/screen firmware upgrade mapping (Process Create and Process Start captures, not filename-based assumption): DeviceDriver.exe -> firmware\L99_中文_V1.31.exe (2,213,280 bytes, SHA-256 E316C25591711D1B425E0BB4F17C02813E70AB9D8CD982D91EA331222112276D; keyboard controller USB HID 0C45:800A) and DeviceDriver.exe -> firmware\L99_ISP_中文完整UI_V1.23_156.exe (162,852,672 bytes, SHA-256 0A77055429DA60E35AFE419A367BE1AB987B7E3F4CA3B67477BD017AA097FC55; screen interface EEEF:268A virtual COM; screen controller family under investigation LT268A/LT2686 UartTFT).
- Recorded screen updater launch-only findings: launched without pressing Start; no firmware upgrade or intentional flash write; nineteen preserved evb*.tmp files, each exactly 1536 bytes, each beginning with an MZ header; strings included "This program must be run under Win32", "ntdll.dll", "ZwOpenFile"; all nineteen files had different SHA-256 hashes; small PE/helper stubs, not complete screen firmware payloads; pattern consistent with an Enigma Virtual Box style virtualized runtime but packer identity not conclusively verified; one zero-byte evb*.tmp remained locked by the running updater and was not forcibly copied; no large firmware image observed extracted into a normal TEMP file.
- Recorded extraction inventory: HFD_ISP_TOOL_V1.31.exe (99,328 bytes, SHA-256 3FD0227368539E4B80A385EA721A1F091D6F22997DA24451E2F8248D512CA282; matching copies under evbunpack_output and firmware\unpacked); HFD_Code_V2.2.bin (305,800 bytes, SHA-256 432E358CAC96FB930AB680ADA6F953C9005027C58B31B7EE3BB6BC7868EF35CF; matching copies under evbunpack_output, firmware\unpacked, and the local softce working tree); Chinese 1.0.1.4 HFD_Code_V2.3.bin variant (313,504 bytes, SHA-256 B277823234FCAB7137963896493BCB6896FD985FC972354166FCFC584534E37F); other local HFD_Code_V2.3.bin variant (313,652 bytes, SHA-256 A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03); Flash.ini (1,571 bytes, SHA-256 E515905C61A6AD99BF96EAAC3E24E5CFD21E274C087F9903B14F35ECECE21E2C).
- Recorded Flash.ini purpose: flash-chip geometry database listing JEDEC IDs, page sizes, page/block counts, and chip models for supported SPI NOR and SPI NAND devices (Winbond, GigaDevice, XTX, Macronix, and related); contains no firmware filenames, no HFD_Code_V2.2.bin/V2.3.bin selection logic, no UartTFT-II_Flash.bin selection logic, no L99 model mapping, no firmware destination addresses, no firmware version-selection rules; not a payload-selection configuration.
- Recorded verified comparison of the two HFD_Code_V2.3.bin variants: size difference 148 bytes; common prefix 0 bytes; first difference at offset 0x0; differing offsets in overlapping range 286084; common suffix 22 bytes — genuinely different builds or variants, not one file with a simple 148-byte trailer.
- Corrected and recorded official UartTFT-II_Flash.bin provenance: downloaded directly from the official AULA website during the initial research (127,599,044 bytes, SHA-256 4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4); current local working path tools\softce-aula-l99-research\extracted\UartTFT-II_Flash.bin is only a working location used for analysis and must not be interpreted as file provenance; not extracted from the softce repository, not distributed by the softce repository, not extracted from the Chinese 1.0.1.4 updater, not produced by evbunpack, not recovered from a process memory dump; website URL and exact download timestamp are not claimed as known.
- Recorded softce research context: softce documentation reports modifying resources, page descriptions, and touch records in a file named UartTFT-II_Flash.bin; softce repository does not distribute complete factory or modified BIN files; local official UartTFT-II_Flash.bin was copied into the softce working directory for analysis; local directory path must not be used to infer provenance.
- Recorded official full-flash sample comparison: read-only raw containment test between L99_ISP_中文完整UI_V1.23_156.exe and official UartTFT-II_Flash.bin returned FULL_RAW_MATCH: NO; the official UartTFT-II_Flash.bin is not stored verbatim as one contiguous uncompressed block inside the Chinese 1.0.1.4 screen updater; this does not invalidate official provenance; possible explanations (compressed or encrypted storage, Enigma virtual-file packaging, segmented storage, runtime reconstruction, different official builds or delivery packages) remain unproven.
- Added completed-work, do-not-repeat, unresolved-questions, safety-status, next-planned-task, and scanner-requirements sections to docs/PROJECT_HANDOVER.md, including a pasteable new-chat starting prompt.

### Corrected
- UartTFT-II_Flash.bin provenance corrected: official AULA website download; the local softce working-directory path under tools\softce-aula-l99-research\extracted\ must not be interpreted as file provenance, and no claim is made that the file came from softce, evbunpack, the Chinese 1.0.1.4 updater, or a process memory dump.

### Safety
- Firmware work remains read-only. Do not press Start in either updater. Do not flash either HFD_Code_V2.3.bin variant. Do not write the official UartTFT-II_Flash.bin. Do not enter bootloader mode solely for experimentation. Do not replay upgrade traffic. Do not modify updater executables. Do not treat the existence of an official image as proof that recovery is safe. Brick risk remains material until flash layout, validation logic, write sequence, and recovery method are verified.

### Verified
- git diff -- CHANGELOG.md docs/PROJECT_HANDOVER.md reviewed.
- All required hashes, verified mappings, corrections, and safety status present in updated documentation; all newly added content is English only.

## v0.6.2 - 2026-11-10

### Added
- Firmware upgrade process mapping confirmed via Process Monitor captures for installed Chinese AULA L99 version 1.0.1.4.
- Main application: `DeviceDriver.exe` (1,837,056 bytes, SHA-256 `DD9C934E2F6F1CC53AE4AFB5B412C3F696CD4D329A03DF28BD151DAB90B3E6B3`), PID 5652 parent for both upgrade entries.
- Keyboard firmware upgrade: `firmware\L99_中文_V1.31.exe` (2,213,280 bytes, SHA-256 `E316C25591711D1B425E0BB4F17C02813E70AB9D8CD982D91EA331222112276D`), child PID 27840.
- Screen firmware upgrade: `firmware\L99_ISP_中文完整UI_V1.23_156.exe` (162,852,672 bytes, SHA-256 `0A77055429DA60E35AFE419A367BE1AB987B7E3F4CA3B67477BD017AA097FC55`), child PID 16676.
- Verified process hierarchy: `DeviceDriver.exe` -> keyboard `L99_中文_V1.31.exe` / screen `L99_ISP_中文完整UI_V1.23_156.exe`.

### Safety
- No firmware upgrade started.
- No bootloader transition or flash write performed.
- Read-only analysis only.

## v0.6.1 - 2026-11-10

### Corrected
- Corrected the official-update capture toolkit so the only approved capture target is the original untouched L99 ISP V1.23.exe package (`firmware\unpacked\L99 ISP V1.23.exe`, 111,008 bytes, SHA-256 `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0`), previously used successfully twice on this keyboard.
- Do NOT capture or execute the 2026-05-25 Screen Reset EXE from L99-reset.zip.
- L99-reset.zip remains offline extraction and recovery-reference material only.
- Do NOT use patched_UartTFT-II_Flash.bin.
- Do NOT construct a new UI-only package.

### Added
- `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md` now records the L99 ISP V1.23.exe package path, filename, size and SHA-256; inventories every file beside the EXE (core package files, runtime DLLs, subdirectories, external UartTFT-II_Flash.bin reference); explicitly rejects the Screen Reset EXE, patched UI images, renamed/replaced vendor payloads, and missing expected package files; generates Procmon filters for the real EXE and expected child processes; provides USB controller (EEEF:268A) identification instructions; scopes capture questions to what L99 ISP V1.23.exe actually reads, extracts and transmits; states this capture does not verify the reset-package updater or modified UI acceptance.
- `scripts/prepare_official_capture.ps1` `-Preflight` command: performs no hardware access, launches no EXE, verifies package hashes, verifies Procmon/Wireshark/USBPcap availability, verifies adequate free disk space, creates an empty timestamped capture directory, prints READY or NOT READY.
- `scripts/analyse_official_capture.py` updated: manifest keyed to L99 ISP V1.23.exe package (including HFD_Code_V2.3.bin earlier build 313,504 bytes `b2778232...`), detects process and child-process names without launching, generates Procmon filters for the real EXE and expected child processes.
- `tests/test_analyse_official_capture.py` updated: synthetic package-root fixtures, manifest verification (pass/missing/mismatch), child-process detection, Procmon filter generation.

### Changed
- Release bumped to v0.6.1 (was v0.6.0).
- Decision remains NO-GO for modified firmware.
- docs/PROJECT_HANDOVER.md, docs/CONTROLLED_FLASH_PLAN.md, docs/RECOVERY_COMPATIBILITY_MATRIX.md updated to reflect L99 ISP V1.23.exe as sole capture target and excluded targets.

### Verified
- PowerShell syntax check passes on `scripts/prepare_official_capture.ps1`.
- `py_compile` passes on all scripts and tests.
- All repo tests pass (`python -m unittest discover -s tests`).
- `git diff --check` passes.
- No vendor/capture/generated files tracked.
- No staged file over 5 MB.
- NO-GO requirements not weakened.

## v0.6.0 - 2026-11-10

### Added
- Added `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md` — passive capture procedure for one unchanged official AULA L99 screen update. Answers ten questions static analysis cannot verify: files opened, HFD V2.2/V2.3 read, UartTFT-II_Flash.bin read independently, exact file-open and read order, exact USB command and transfer order, UI vs HFD payload transmission, total bytes per payload, re-enumeration/ISP entry, FileCRC/FlashCRC behavior, final success and restart sequence.
- Added `scripts/prepare_official_capture.ps1` — verifies official file hashes, absence of `patched_UartTFT-II_Flash.bin`, no updater running, no tracked vendor/capture files over 5 MB. Capture preparation only; never runs the updater, never accesses hardware, never flashes.
- Added `scripts/analyse_official_capture.py` — offline analyser for exported Procmon CSV + USBPcap/Wireshark PCAPNG. Inventories opened firmware files and read order, calculates bytes read per file, identifies HFD V2.2/V2.3/UI access, reports USB transfer sizes/sequence/timing, distinguishes EVIDENCE from INFERENCE. Never opens COM/USB/HID, never executes an updater.
- Added `tests/test_analyse_official_capture.py` — synthetic analyser tests (no vendor firmware, no hardware, no COM/USB access).

### Changed
- Release bumped to v0.6.0 (was v0.5.0).
- Decision remains NO-GO for modified firmware.

### Verified
- PowerShell syntax check passes on `scripts/prepare_official_capture.ps1`.
- `py_compile` passes on all scripts and tests.
- All repo tests pass (`python -m unittest discover -s tests`).
- `git diff --check` passes.
- No vendor/capture/generated files tracked.
- No staged file over 5 MB.
- Factory `UartTFT-II_Flash.bin` unchanged (SHA-256 `4cb3fa5c...`).
- NO-GO requirements not weakened.

## v0.5.0 - 2026-11-10

### Added
- Added `docs/VENDOR_FIRMWARE_PROVENANCE.md` — official vendor firmware provenance record: official listing URL, direct ZIP URL, filename, size (45,080,624 bytes), SHA-256 (`e854bebb...`), discovery reference (softce/aula-l99-research docs/recovery.md), note that URL directory `20240621` is not the release date, ZIP can reproduce `UartTFT-II_Flash.bin` via the hash-locked extractor, private backup recommendation, and statement that vendor binaries are not redistributed in the public repository.
- Added `vendor/vendor_files_manifest.json` — vendor file manifest (sizes and SHA-256 only; binaries not redistributed). Records official package, all vendor files with hashes, exact UI-only package layout (`HFD_ISP_TOOL_V1.31.exe` + `UartTFT-II_Flash.bin` at package root, `Flash.ini` optional, HFD_Code files can be omitted), HFD optional/required conclusion, interrupted-write recovery conclusion, and decision.
- Added exact UI-only package construction conclusions to `docs/UI_ONLY_PACKAGE_CONSTRUCTION.md`: required filenames and relative paths, `Flash.ini` not required, HFD_Code files can be omitted, absence of HFD files selects UI-only mode per softce (STRONG_INFERENCE, not VERIFIED), HFD write order before/after UI UNKNOWN, interrupted update can re-enter ISP via manual re-entry (STRONG_INFERENCE) / automatic recovery UNKNOWN.
- Updated `docs/RECOVERY_COMPATIBILITY_MATRIX.md` — UI-only package layout table, interrupted-write recovery conclusion with ISP entry/timeout/restart/retry paths, manual re-entry vs automatic recovery distinguished.
- Updated `docs/CONTROLLED_FLASH_PLAN.md` — UI-only package layout section and recovery path conclusions.
- Updated `docs/PROJECT_HANDOVER.md` — vendor provenance and UI-only package layout references, expanded milestone findings.

### Changed
- Release bumped to v0.5.0 (was v0.4.1).
- Decision remains NO-GO unless exact UI-only package acceptance and ISP re-entry are VERIFIED.

### Verified
- All 96 repo tests pass (`python -m unittest discover -s tests`).
- py_compile passes on all scripts and tests.
- Factory `UartTFT-II_Flash.bin` unchanged (SHA-256 `4cb3fa5c...`).
- No ZIP, EXE, BIN, PNG, or extracted assets added to Git.
- No live updater folder constructed.
- Patched BIN unchanged.
- No global checksum deep scan re-run.
- NO-GO requirements not weakened.

### Resolved blockers (documentation only)
- Exact UI-only package layout documented as STRONG_INFERENCE (required: `HFD_ISP_TOOL_V1.31.exe` + `UartTFT-II_Flash.bin`; optional: `Flash.ini`; excluded: HFD_Code files).
- HFD optional/required conclusion: HFD_Code files can be omitted; absence of HFD files selects UI-only mode per softce (STRONG_INFERENCE); not VERIFIED by static analysis.
- Updater rewrites HFD before/after UI: UNKNOWN.
- Interrupted-write recovery: automatic software recovery UNKNOWN; manual re-entry into ISP STRONG_INFERENCE (official instructions: power cycle, Fn+X->0->6, Fn+Space; one configuration only, not universal).
- Vendor firmware provenance documented (listing URL, direct ZIP URL, filename, size, SHA-256, URL directory date != release date, hash-locked extractor reproduction, private backup recommendation, no redistribution).

### Remaining blockers (critical)
- Image-level self-checksum within `UartTFT-II_Flash.bin`: UNKNOWN (per-packet CRC verified; image-level self-checksum not located).
- Exact UI-only package acceptance: STRONG_INFERENCE only; not VERIFIED.
- Recovery behavior after interrupted write: UNKNOWN.
- Until all critical blockers are VERIFIED, no hardware write is permitted.

## Unreleased

### Added
- Optimised `scripts/flash_checksum_scanner.py` with `--mode quick` (targeted structural checks, no exploratory whole-image candidate scanning, target under 30 seconds on the 127,599,044-byte factory image) and `--mode deep` (full structural investigation, cached by factory hash, patched hash, scanner version, scanner source hash, algorithm list, and region-map hash). Cache hit returns immediately. Uses native C-backed CRC32 (zlib), lookup-table CRC16/MODBUS and CRC32/standard, ProcessPoolExecutor parallelisation across `min(8, physical CPU cores)` workers (never ThreadPoolExecutor for CPU-bound work), single full-image read, per-region single algorithm computation, configurable `--max-runtime` guard, and phase/progress/timing output.
- Added synthetic tests for quick/deep modes, cache creation, cache-hit on identical key, cache invalidation on changed scanner version/source hash/algorithm list/region map, deterministic cached output, false-positive CRC16 collision handling, timeout guard, source-image immutability, and multiprocessing/single-worker equivalence.
- Deleted `scripts/analyze_updater_pe.py` (was a one-off PE analysis tool, not a reusable checksum scanner; no longer needed now that PE analysis results are documented).
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
- C14 Flash JEDEC/model checks: STRONG_INFERENCE (Flash.ini JEDEC->chip mapping; `0xEFAA21` string).
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
## 2026-11-19 - E30a, E33, E34 results (offline and read-only, no hardware access)
- E30a (EVIDENCE): tested library matcher, parser self-test passed. Firmware C1/C2/C3 contain 91/91/90 unique library functions byte-identical to the vendor mcore-elf libraries (about 11 percent of the code region). Divide-enabled multilib (top level = c0_div) matches 7 more functions than c0_nodiv (84 vs 91, 13004 bytes), so the firmware was built with the default divide-enabled C0 multilib, little endian. Relocation-derived __malloc_av_ = 0x800D68 / 0x800D64 / 0x800D54 equals the self-pointer address derived separately. Matched names include _malloc_r, _free_r, _realloc_r, memcpy, memset, strlen, strcmp, _svfprintf_r, siprintf, floorf, powf, sqrtf, _sbrk, _write.
- E33 (EVIDENCE): alignment C1 vs C2 91.1 percent, C1 vs C3 87.3 percent. V2.3-only block of 8000 bytes at C1 0x0FAB8-0x119F8 (present in both V2.3 builds). V2.2-only insertion of 364 bytes at about C3 0x06E02 near the flash chip name strings (INFERENCE: chip name table). Last 2252 bytes of each file = 1092 + 1160 (data image). Correction: the 148 byte size difference is not in the tail.
- E34 (EVIDENCE with corrections): K frame as sent: idx0 K, idx1 param, idx2-3 LT, idx4-7 time, idx8-11 CRC32 (identifier only keys the CRC, not sent), idx12-13 E8 17, idx16 baud class (7F for 921600 else 08). Reply CRC32 is recomputed over idx0-15 with the identifier at 8-11 and the tag word 0x4C544F50 (POTL) at 12-15, compared with reply bytes 1-4. Reply type words 0xEEBA0080/0xEEBA0081/0xEEBA0020. Flash-id request is 6D 01 pp then zeros (CONCAT12 puts param_1 in the high byte); reply marker 7D then the id as little endian u32; id is looked up in Flash.ini section FLASH. DeviceDriver search remains invalid: the decompile lists constants in decimal (CONST lines).
- Corrected earlier reports: E34 K frame indexes shifted by 4, E34 flash-id query byte order, E33 size accounting, E26 positive return value of the handshake function.
- Open: E32 report missing. Next: E32 rerun, E35 (handshake literals in HFD), E36 (describe unmatched ranges), E37 (K callers, Flash.ini lookup, DeviceDriver decimal constants).
- Direction unchanged: custom firmware. SAFE_FLASH_NOT_READY.

## 2026-11-19 - E32 flag routine, E30a library proof, data image layout (offline and read-only, no hardware access)
- EVIDENCE: relocation-derived symbol addresses (65 named symbols, one address each) equal base 0x60010000 plus the file offset of the matched library bodies for 50 symbols, 0 conflicts. Link base and linear layout of C1 are proven for the library region by a method independent of the vector table. The updater long-branch rotation cannot be the runtime layout (it would overwrite CRC table bytes 0x320-0x4FF).
- EVIDENCE: library code spans C1 0x6E70-0xF934 (91.9 percent byte-identical). Reset routine at 0x7490 lies inside it. Application code follows at about 0xF934.
- EVIDENCE: lrw (register bits 11-8, offset bits 7-0) and jsri/jmpi use pool = ((pc+2) AND -4) + 4*offset. Checked on the reset routine and on all 584 call graph rows. Earlier audit script decoded lrw wrongly (E32 verdict LRW_FORMULA_NOT_DETERMINED was a tool bug).
- EVIDENCE: function at 0x60036E30 loads 0x6000F000 (lrw r2 at 0x60036E3E) and 0x40130000 (lrw r6 at 0x60036E50) and calls 0x60047E68, 0x60047E8C, 0x60048170. INFERENCE: update flag write followed by watchdog use. Callers unknown.
- Data image of C1 starts at or before 0x4C07C (impure_data 0x4C080, malloc bins 0x4C4AC = RAM 0x800D68, __fdlib_version = last word = RAM 0x8011EC). RAM end is 0x8011F0. Corrects the earlier end 0x8011E8 and the multibyte length reading.
- Name corrections: 0x60019600 is _sbrk_r, compare functions __nedf2/__ltdf2/__ledf2/__gesf2/__ltsf2 by relocation.
- New tools: aula_poolref.py, aula_callers.py. New file: C1_library_labels.csv (129 rows).
- Next: E38 (callers), E39a (decode routine and callees), E39b (start-up and data copy parameters). Pending: E35, E36, E37.
- Direction unchanged: custom firmware. SAFE_FLASH_NOT_READY.

## 2026-11-19 - E38, E39a, E39b: start-up parameters and flag routine callers (read-only, no hardware access)
- EVIDENCE: start-up routine (C1 0x60045150) loads five literals: data copy source 0x6005BF44 (file 0x4BF44), RAM 0x800800-0x8011F0 (2544 bytes), bss 0x801200-0x870E6C. Source plus size equals the file size exactly in C1 (0x4C934), C2 (0x4C8A0) and C3 (0x4AA88). Corrects the earlier data image start estimate 0x4C068 and the E39b statement that sizes disagree (0x4C934-0x4BF44 = 0x9F0).
- RAM map C1: data 0x800800-0x8011F0, bss 0x801200-0x870E6C (457836 bytes), stack top 0x874FFC (16784 bytes above bss end).
- Call chain: reset 0x60017490 -> main 0x600449B0 -> 0x60021994 -> 0x60036E30 (flag routine). Main loads 115200 into r3 before its second call (0x60049C18).
- Flag routine 0x60036E30: r2 = 0x6000F000, r3 = stack pointer, r4 = 4, callee B 0x60047E8C loads 0x60200000 (2 MB flash end), callee C loads 0x400E0000/0x400E006C, watchdog base 0x40130000. Same decoded shape in C1, C2, C3 (pool values differ). INFERENCE: 4-byte flash access with bounds check; read or write not shown.
- V6 call graph is incomplete (4 literal references to 0x60036E30 vs 1 csv edge).
- V2.2 conflict: C3 base is 0x6000A000, so 0x6000F000 lies inside the C3 image (file 0x5000); in V2.3 it lies 0x1000 below the image.
- Interrupt rule (vector 32+n = source n): RGBC vector 57 loads 0x401A0000 (match). Vectors 32, 35, 36 load 0x40110000, 0x400A0000, 0x400B0000 (bases not in the known list). Seven large handlers still untested.
- Next: E40 (decompiled text, REA), E41 (handlers, callers, literal counts), E36, E35. Pending: VirusTotal results, datasheet memory map pages.
- Direction unchanged: custom firmware. SAFE_FLASH_NOT_READY.

## 2026-11-19 - E43 results: flag routine, flash helper, boot logic (read-only, no hardware access)
- EVIDENCE (Ghidra decompiled text, V2.2 C3 and V2.3 C1): flag routine (C1 0x60036E30, C3 0x6002F01C) copies a 1396 byte flash helper to RAM, calls the flash write helper with (0x6000F000, &0xFFFFFFFF, 4), clears PWM1 bits, writes IER=0 and WDT+2=0, then jumps through the word stored at the address its caller passes (0x60000000, flash start). INFERENCE: entry into the bootloader / update mode; the bootloader is not in any HFD file.
- Flash write helper (C1 0x60047E8C, C3 0x6003FC74): range check against 0x60200000, cache module off, parameter block at RAM 0x800600-0x8006C0, calls RAM code at 0x800004. Used with sector aligned addresses and 70 byte records by the settings writer, so it erases and programs.
- Settings store: 200 slots x 4 KiB at 0x60081000-0x60149000, 70 byte records. The ring end shows the internal flash is the 2 MiB part (INFERENCE, UNVERIFIED).
- Correction: the flag routine does NOT run on every start. V2.2 main runs it only if the external flash id is not 0xEFAA21 / 0xC89101; V2.3 runs it when detection 0x60021818 returns 0.
- V2.2 recognises W25N01GV (0xEFAA21); none of the four V2.3 ids seen equals it. V2.2 is now the working baseline for the unit (INFERENCE).
- V2.3 only block 0x0FAB8-0x119F8 holds the flash detection table (0x60021818) and the 0x104 byte configuration block reader (0x60021994).
- Interrupt rule confirmed by IER bits: bit 28 (SCI1) around UART init, bit 30 (EPORT0) around a wait loop.
- Correction: E43 package seed isr_usb for C1 used a file offset (0x60037D10); the vector 46 handler is 0x60047D10. C3 0x6003FAF8 is correct. Pool variable resolution in L99DecompAt.java matched the wrong names.
- Next: E44 (REA, detached package: call tree decompile), E45 (UI image header CRC probe), E46 (RAM blob, data image, clock, flag sector bytes). Pending: E37.
- Direction unchanged: custom firmware. SAFE_FLASH_NOT_READY.

## 2026-11-19 - E44/E45/E46 results: stock command protocol, update-mode entry, display and flash facts (read-only, no hardware access)
- EVIDENCE (C3 decompiled text): the flag routine is reached from main (unknown flash id), and from both command parsers when system register 0x2011 is written with AA 55. The RAM flash helper (188 bytes, identical in C1 and C3) erases the 4 KiB sector at flash offset 0xF000 and programs 0xFFFFFFFF; in V2.2 that sector is inside the application (image offset 0x5000). HAZARD: never write register 0x2011.
- Stock firmware is an HMI engine: frame 5A A5 len func addr data CRC16; func 0x03 read, 0x10 write, 0x41 touch events; 0x2000 page, 0x2001 brightness, 0x2002 RTC, 0x200B volume. No host pixel upload command seen (INFERENCE).
- Display: 16-bit writes to the external bus 0x20000000/0x20000002, ST7796S style init. RGB controller handler is a debug stub: frame buffer candidate 0x875000 withdrawn. LT168B still favoured (16-bit external bus, 2 MiB flash ring), unverified.
- External flash is SPI NAND (0x9F, 0x13, 0x0F/0x1F, 0x6B, 2 KiB pages); V2.2 continues only for ids 0xEFAA21 and 0xC89101. Internal flash: NOR commands 0x06/0x05/0x20/0x02.
- Corrections: early init sets the clock (12 MHz to 168 MHz, 0x6003EECC(168)); settings marker is 0x94; PWM1 is the audio output; E45 premise was wrong (config block is 0xF4 bytes at flash offset 0x80 with a salted CRC-32).
- E45: no 256-byte plus CRC-32 block in the first 16 MiB of either UI image. E46: RAM helper identical in both builds; clock word 168000000.
- Next: E47 (local, config block test), E48 (REA package, command path and SD update strings). SAFE_FLASH_NOT_READY.

## 2026-11-19 - E47/E48: frame buffer confirmed, config block, protocol cross-check (read-only, no hardware access)
- EVIDENCE: page canvas pointer is 0x00875000 in V2.3 (RAM 0x800934) and V2.2 (RAM 0x800920). Page render draws RGB565 into the canvas, then DMA pushes lines to the panel data register 0x20000002; a blit (V2.3 0x60057230) copies canvas regions. 307200 bytes ending at 0x8C0000.
- E47: both UI images carry a valid config block at offset 0x80 (complement pair and salted CRC-32 init 0 match). Same reader in V2.3 (0x6004D4F0). Block bytes 12-13 = 5A A5, bytes 16-19 = 40 01 E0 01.
- Registers: 0x2040 orientation (panel command 0x36 with 0x48/0xA0/0x88/0x60, swaps width and height), 0x200A sound, 0x203F preset load. PWM1 +0x34 = backlight duty (64 level table at RAM 0x800816, 0..500), callee C of the flag routine turns the backlight off.
- Protocol: firmware frame 5A A5 len func addr data CRC16; vendor note frame Start cmd nn params CRC End4 with commands 0x80..0xF6. Parser handles 0x03 and 0x10 itself; other codes go to an unresolved indirect jump (0x6004281C etc.). Not resolved.
- Correction: V2.3 recognises eight NAND ids (incl. 0xEFAE21); V2.2 recognises 0xEFAA21 and 0xC89101. Updater picks V2.2 only for 0xEFAA21. Which build the unit runs is open again.
- V2.2 has SD card flasher strings; V2.3 does not. V2.3 0x60021994 reads a 0x104 byte block (page 0, col 0, CRC-32) probably a bad block remap table, not part of the UI image.
- Next: E49 (REA agent prompt, dispatcher listing). E50 (local, SD strings by value). Pending: E37.
- Direction unchanged. SAFE_FLASH_NOT_READY.

## 2026-11-19 - E49: parser dispatch resolved; upload capture is the native extended frame (read-only, no hardware access)
- EVIDENCE (V2.3 listing): USB parser 0x60041E14 handles function 0x03 and 0x10 itself; every other normal frame goes to 0x6004281C which knows only 0x61 (sub-commands 0-6) and 0x62 (only when current page is 0x12). Vendor note command set 0x80-0xF6 is NOT implemented by the parsers.
- Native frame: 5A A5, then first byte; non-zero = normal [len][func][payload][CRC16 lo hi]; zero = extended [00][len hi][len lo][func][payload][CRC16 lo hi]. CRC covers func+payload. Capture frames map: data 00 08 07 64 (length 0x0807 = 1+4+2048+2, func 0x64), short 00 00 12 64, commit 00 00 0B 66 (func 0x66). Earlier labels "cmd 07/12/0B" and "const 64/66" were wrong (low length byte and function code); byte strings and CRC unchanged.
- Extended functions: USB parser 0x64 write (address must be above 0x03FFFFFF; slot starts 0x04000000+k*0x60000 and 0x04240000 begin a new image; staged total = record size + 11 = 307211), 0x66 commit (calls 0x6002148C, 128 KiB blocks), 0x67 status. Serial parser also 0x61 (sector write at address+0x0804B000), 0x62 (read), 0x63 (CRC-32 of flash range), 0x65 (NAND read). Replies: func, FF, func, address, 'O','K'.
- Page render confirmed: canvas 0x875000 mode byte 2, base picture + widgets, DMA push to 0x20000002; region blit 0x60057230.
- No host pixel push command exists in the stock parsers. HAZARD: never send extended frames 0x61-0x67 or function 0x61 to a unit.
- Next: E50 (REA agent, commit/CRC/send helpers, 0x61 sub-commands, drawing primitives). Pending: E37; hardware step (read flash id) decides G7.
- Direction unchanged. SAFE_FLASH_NOT_READY.

## 2026-11-19 - E51 results: PC updater protocol, flash helper guard, peripheral census (read-only, no hardware access)
- EVIDENCE (updater decompile): MCU update sequence K('0'), K('1'), L(start,end), J frames in 0x800 byte chunks ascending, N(length,CRC). For identifier 0x1971268A the start is 0 and the end is the file size. 64 byte pieces: 4A 30 (addr, len, up to 56 bytes), 4A 31 (62 bytes), 4A 32 (rest). CRC-32 init 0, no final xor. No erase frame; the PC tool never writes 0x6000F000 (V2.2 file carries 00000000 at image offset 0x5000).
- Rotation is conditional (size >= 0x5C01 and a string predicate false), same predicate as the trailer CRC check; raw HFD files are not rotated. Earlier rotation reasoning (v11, v13) withdrawn.
- UI image: length at 0x174, CRC-32 at 0x178, complement at 0x17C, blanked to FF by the tool. UI data frames j/k/l, marker 7C, verify n.
- Flash helper (V2.3 0x60047E8C, V2.2 0x6003FC74): returns 0 ok, 1 above 0x60200000, 2 below 0x60000000; NO lower guard against the bootloader area. Custom firmware needs its own guard.
- Application never arms the watchdog: only writes 0 to WDT+2 (early init, flag routine). EPORT1, EPORT2, SCI0, SCI2, CCM, RCM not used. EPORT0 only for touch (GT911 class sequence, I2C 0x28).
- Datasheet: PGMCK and PGMIO are the default function of pins 64 and 57 (LT168B and LT168C), shared with RXD2 and TXD2; pads DIO and SCK are very likely this programming port (INFERENCE).
- Commit 0x66 (V2.3) programs the external NAND through a bad block table and returns CRC; V2.2 0x66 reads back and returns CRC; 0x67 bad block status.
- Next: E52 (REA package): static analysis of L99_ISP_CNUI_V1.23_156.exe and L99_CN_V1.31.exe. SAFE_FLASH_NOT_READY.

## 2026-11-20 - E52 results and official update page (read-only, no hardware access)
- Official page (aulastar announcement 788): keyboard firmware with "L99 Keyboard Reset Firmware Update Tool", then screen firmware: hold FN and press X, 0, 6 to put the screen into update mode, then run the screen tool. Package "L99 Reset Firmware 2026.05.25". HAZARD: the combination erases the flag sector (inside the application in V2.2).
- L99_CN_V1.31.exe is a SONiX USB MCU ISP tool (keyboard, SN8 files, VID 0C45), not a screen tool. L99_ISP_CNUI_V1.23_156.exe is the Levetop Qt screen tool packed with Enigma Virtual Box (inner name HFD_ISP_TOOL_V1.31.exe; contains Flash.ini, HFD_Code_V2.2.bin, HFD_Code_V2.3.bin). raw_isp_v123 text comes from it.
- Screen protocol corrections: UI 'j' frame has a 1 byte length (max 0x39), data up to 57 bytes; K parameters '0','2' for the UI path; K byte 14 = 0x7F at 921600 baud else 0x08; device words 0xEEBA0080/81/20 select per-chunk delays 125/50/125 ms. Flash.ini line = id,n1,n2,name (size = n1*n2).
- Nine ids 0x1971168A/B, 0x1971268A-D, 0x19712690, 0x19717689, 0x19717760 (names LT168A/B, LT268A-D, LT2690, LT7689, LT776). 268x is a bootloader family name; the chip is LT168 class (LT268A has 72 MHz, 64 KB flash, 8 KB SRAM and cannot match). LT168B still favoured, unverified.
- Hardware rescue lead: Levetop LT268 manual enters upgrade mode with BUSY pin to ground plus reset (development board); L99 SW2 or pads may be the same strap (INFERENCE).
- Next: E53 (REA package): official reset tools "L99 keyboard Screen reset firmware.exe" and "L99 keyboard reset firmware.exe". SAFE_FLASH_NOT_READY.

## 2026-11-20 - E53: official 2026.05.25 reset tools (static analysis, read-only, no hardware access)
- Screen tool "L99 keyboard Screen reset firmware.exe": code sections equal to L99_ISP_CNUI_V1.23_156.exe; only Enigma-packed data differ. Contains HFD_Code_V2.2.bin and HFD_Code_V2.3.bin byte-identical to the analysed files (no new MCU code). Compile time stamp 2026-04-07.
- Four embedded UI images: head 4 KiB differ in 22 bytes (config block bytes 0..5, complement pair 0x16C..0x173, CRC 0x178..0x17F). One has the factory CRC 0x7782E947, three have 0xE2CE3EF9 (same as V1.23_156). Header length 10,704,364 bytes (10.2 MiB) covers only the first part of the 127.6 MB factory file; header CRC rule (length at 0x174, CRC 0x178, complement 0x17C, 12 bytes set to FF) verified for all four.
- Flash.ini identical in both tools (50 lines, 15 SPI NAND). All V2.3 NAND ids named: A1F1A1 TX25G01, C8D1C8 GD5F1GQ4UB, CDEA11 FS35ND01G, EFAE21 W25N01KV, C891C8 GD5F1GM7UE, 0B710B XT26G01F, 5EA1A1 ZB35Q01CYIG, 0B1100 XT26G01C; V2.2 ids EFAA21 W25N01GV and C89101 (not in Flash.ini). Build for the unit still depends on the NAND id.
- Keyboard tools: "L99 keyboard reset firmware.exe" = L99_CN_V1.31.exe code and data; same SN32F290.hex (259282 bytes, SHA-256 43fe9a72768215a1394a9808d23cd12792da0b45ccc0c99195ab58abe0140c38). Only UISettings.ini texts differ. Keyboard MCU SN32F290 (VID 0C45, PID 7141/7140), hex starts with SP 0x20002B18 and reset vector 0x00007EE5 (Cortex-M class, INFERENCE).
- Correction: UI image proper is 10.2 MiB; the need for a NAND follows from the data area at 64 MiB and above, not from the file size.
- Next: upload SN32F290.hex (3 parts) for the keyboard to screen command path (FN X 0 6). SAFE_FLASH_NOT_READY.

## 2026-11-20 - SN32F290 keyboard firmware rebuilt and first analysis (static, no hardware access)
- SN32F290.hex (official keyboard reset tool) rebuilt from 3 uploaded parts: 5766 records, 0 checksum failures, contiguous image 0x00000-0x167F3 (92148 bytes, SHA-256 a805de868dfe27de39ff003dbf9c56347fa4e0441d0150a8a6802280c9872799), option bytes 55 55 AA AA at 0x3FFFC. SP 0x20002B18, reset vector 0x00007EE5 (Thumb). Cortex-M0 class.
- USB device descriptor in the image: VID 0C45 PID 8801 (SONiX, USB KEYBOARD). Live keyboard noted as 0C45:800A, so the image is the reset build (or has a second descriptor set); PID after update to be checked.
- HID: keyboard, consumer (id 3), system (id 2), key map (id 1), mouse (id 6), vendor id 5, vendor page 0xFF13 with 64 byte input/output/feature reports (host channel).
- UI strings and an ST7735 style LCD init: tri-mode keyboard (USB, 2.4G, BT1-3) with its own status display (INFERENCE).
- Frame header 5A A5 NOT present in the keyboard firmware; FN X 0 6 handler not located by pattern search. Earlier statement that the keyboard sends register 0x2011 AA 55 is unproven.
- Next: E54 (REA package, Ghidra ARM text dump of the keyboard firmware). SAFE_FLASH_NOT_READY.

## 2026-11-20 - E54 results: keyboard firmware SN32F290 decompiled (static, no hardware access)
- Ghidra (ARM:LE:32:Cortex) created 225 functions, 224 decompiled. FN X 0 6 handler NOT found. No code builds frames for the 3.98 inch screen; the Modbus style header 5A A5 does not occur.
- The only UART (0x40054000) is a wireless module link: keyboard to module A1 (8 byte boot report), A2 (14 byte key bitmap), A3 (consumer), A4, A5, A6 (mode 0x11, 0x30, 0x31-0x35), A8 (pointer), A9 (BT name Kzzi-Z98RGB); module to keyboard 5A (LED), 5B (link state), 61 0D 0A. Checksum = sum of bytes.
- Keyboard drives a 160x80 ST7735 class display (images 0x6400 bytes from SPI flash, read command 03), bit banged I2C RTC (0xA2/0xA3, PCF8563 class) and battery gauge (0xC6/0xC7), settings pages 0x8000/0x8400/0x9400.
- Coverage gap: about 183 functions never created (USB ISR vector 24 at 0x8C00, vectors 44/46/47, 0x1330-0x19AB, 0x4400-0x5600, 0xB600-0xD400). FN X 0 6 and the vendor 0xFF13 report handling are probably there.
- Screen update mode from the keyboard: H1 (GPIO or USB path, BUSY like strap) favoured over H2 (serial command); INFERENCE.
- Next: E55 (REA package, create missed functions and decompile with NAME@VALUE pool annotation). Passive check: Device Manager devices by connection. SAFE_FLASH_NOT_READY.

## 2026-11-20 - FN X 0 6 capture (cap4) and K handshake verification (analysis only)
- cap4 is the FN X 0 6 capture (screen tool window open, Start not clicked). 08:15:58.616 key 6 pressed (released after 8 ms), 08:15:58.949 screen (EEEF:268A) re-enumerates (0.333 s later) as the bootloader (serial TEST_1.0, COM4). No USB traffic between keyboard and screen; keyboard does not re-enumerate. Trigger reaches the screen outside USB (INFERENCE: signal line, hub port, or board-internal link).
- Official screen tool: launch sends nothing (cap2). In update mode it opens the COM port itself and sends only 4 K frames (115200 baud x2, 921600 baud x2, class byte 0x08 / 0x7F). No L, J, N frames.
- K handshake model verified on 4 real frames: host CRC = CRC32(init 0, no xor) over bytes 0..7 + identifier; reply CRC = CRC over host bytes 0..7 + device identifier + "POTL"; reply bytes 5..8 echo the host CRC when the candidate is accepted.
- Device identifier is 0x1971168B (candidate 0x1971168A rejected first). Earlier assumption 0x1971268A was wrong. Name pattern: LT168B (INFERENCE). Type word 0xEEBA0081 (mode 1, 50 ms per chunk). Reply bytes 9..12 = 01 17 01 24 (INFERENCE build date 2024-01-17). Pointer 0x60002FB6 shows the bootloader below 0x6000A000. No V v flag: non-V/v frame branch (4 KiB frame) for this unit (INFERENCE, check the decompile).
- Hub tree: keyboard and screen on WCH 1A86:8091 (ports 3 and 2); capture 4 did not include the hub node.
- Next: replug test (screen black?), capture including the hub node, re-read the tool decompile for the group of ids 0x1971168A and 0x1971168B.

## 2026-11-20 - cap5 hub capture and recovery observations
- Update mode (bootloader, EEEF:268A serial TEST_1.0, COM4) is latched: a normal key does not leave it; only a power cycle (USB unplug and replug) returns the screen to the application (COM3). Flag sector not erased. Screen sends no traffic for at least 62 s in update mode.
- cap5 (hub node included): hub status change bitmap 04 (port 2 = screen) at 08:38:16.212 (0.505 s before key 6), at 16.811, 16.931, 16.983 (0.094 / 0.214 / 0.266 s after key 6); screen enumerates at 17.051 (0.334 s after key 6; cap4: 0.333 s). Port 3 (keyboard) never changed; keyboard did not re-enumerate. No hub event during the 10 s idle before the keys. Replug: hub bitmap 0C (ports 2+3), screen enumerates in normal mode.
- Hub class requests (GetPortStatus etc.) are not visible in USBPcap output, so the status bits are unknown. Trigger is not a USB command between keyboard and screen.
- Mechanism open: keyboard-driven supply/USB link toggle in two steps (X 0, then 6) with a boot selection held until power loss, versus an unseen non-USB command link.
- Next: optional FN X 0 only capture (note the key press times), E55 keyboard firmware pass, board photos and datasheet BUSY/BOOT/PGM pages.

## 2026-11-20 - keyboard present in PnP but absent from sync2/sync3 captures
- Keyboard USB\VID_0C45&PID_800A\A&374F4772&0&3 Status OK, parent chain: 1A86:8091 -> three 05E3:0610 hubs -> ROOT_HUB30 -> AMD xHCI (PCI 1022:1639, bus 6 function 4). Screen EEEF:268A shares the same chain and the same capture bus (bus 2), so "keyboard on another root hub" is ruled out. tshark -D lists only USBPcap1 and USBPcap2, both captured.
- Open question: sync2/sync3 show hub (addr 12) and screen (addr 13) but no keyboard descriptor and no HID SET_REPORT/GET_REPORT. Hypotheses: keyboard not enumerated as USB at that time (tri-mode, cable only powering hub and screen) or descriptors/traffic missed at tshark start. Test sync4 with PnP snapshots before/after and a visual note of when the screen shows CPU/GPU.

## 2026-11-20 - screen shows temperature and humidity (re-read of the photo)
- Photo (2026-11-08): page "realtime data": time 09:14:22, date 2026/11/08 Sunday, temperature 8 C and humidity 50 % in one box (thermometer and droplet icons), CPU 5 % and GPU 3 % gauges, no network speed. The earlier claim "keyboard sensor" for the 8 C / 50 % box was retracted: source unknown (weather data, fixed default, keyboard sensor, or app data).
- Frame bytes 14 (45 constant) and 16 (39-43) do not match 8 or 50, so the box is not fed by those bytes; bytes 22..61 are zero in all 41 frames of sync6. Possible sources: the other command frames (04 18, 04 28, 04 02, only the first bytes were reviewed) or a source other than the PC.
- Next: current screen photo (value now, and after closing the official app); print all 64 bytes of the three command frames from sync6.

## 2026-11-20 - LT168 pin note chapters 7 and 10: BOOT and PGM pins (official)
- Chapter 7 (page 16): BOOT/INT1[7] = LT168A pin 24, LT168B pin 34, default EPORT1[7]; "boot-bit detect port, must not be low during power-up". No statement that pulling it low enters an ISP. The earlier hypothesis "SW2 is a BOOT strap" is not supported.
- Chapter 10 (page 21): PGMIO/TXD2/INT2[4] and PGMCK/RXD2/INT2[5] = LT168A pins 37 and 44, LT168B pins 57 and 64; default function PGM download, can be configured as UART2 or EPORT2[4-5] by software (CCM->EPORT2FCR bits 4 and 5, OPTION->CCR). Custom firmware must not reconfigure pins 57/64 if the PGM download port is to stay usable.
- Hardware rescue still open: PGM download protocol and tool, and where SW2/DIO/SCK are wired on the board.

## 2026-11-20 - teardown photos: chip markings confirmed
- Screen sub-board SI-2686-TFT-3.98 V01 (T=1.2MM, 2024.10.11): main chip marked HFD168BDP 2519-L02 (QFN68); flash marked Winbond 25N01GV (2424); 12.000 MHz crystal; touch IC Goodix GT911 (2436-B040) on the display flex; SW2 push switch; four test pads GND, SCK, DIO, RST (probably PGMCK pin 64 / PGMIO pin 57 / reset, NOT verified by continuity); CON2 (SPK+, SPK-).
- Earlier "LT168B" naming corrected: the chip marking is HFD168BDP; its relation to LT168B (Levetop) is inference (768 KB SRAM, 2 MB flash, 168 MHz, QFN68 all match).
- Photo 3 (keyboard main board): MCU marked HFD80CP100 (LQFP100), 229GNWDOa. This conflicts with the earlier assumption that the keyboard MCU is SONiX SN32F290; which board/chip carries the USB controller is unconfirmed.
- S1B agent produced only hit_pages.csv, report.md, MANIFEST.csv (key_pages.txt, key_pages_index.md, questions.md missing); its "verification passed" covered only the three files it wrote. Hit pages: 0x7011 and 0xAA55 on p.128 and p.179; 0x700D on p.128, 177, 220, 303.

## 2026-11-20 - UI_Editor-II manual pages 128, 164-166, 177-179, 181-187 (official)
- Serial command frame: header 5A A5 (configurable), length = cmd(1)+addr(2)+data(2N)+CRC(2), cmd 0x10 write / 0x03 read / 0x41 touch feedback, variable address 0x0000-0x5FFF, write max 0x7D words, read max 0x7C words, data must be an even number of bytes; CRC-16/MODBUS over cmd+address+data only (not header or length), low byte first; fixed ACK 5A A5 04 10 FF 4C 30 (ok) / 5A A5 04 10 00 0C 70 (CRC fail), same for 03 (41 00 / 01 40). Verified with the manual examples (700E=1 -> 5F 00, =0 -> 9E C0).
- Registers: 0x7000 page, 0x7001 brightness 0-63, 0x700B volume 0-16, 0x700C resistive calibration (0x005A), 0x700D key-code trigger, 0x700E auto backlight, 0x700F sleep brightness, 0x7010 sleep time (s), 0x7011 write 0xAA55 = enter serial update mode (needs bootloader support), 0x703F language, 0x7040 portrait/landscape UI, 0x7041 display test 1-3, 0x7042 UI project upgrade (Flash_RW-II), 0x7043 encoder page switch. Our earlier 0x2011/0x2000 numbers were the same registers without the 0x5000 offset.
- Touch feedback: 5A A5 07 41 FF FF <returnValue 2 bytes> <CRC>, address fixed 0xFFFF for button-like controls, returnValue set by the user in UI_Editor (reportToHost is off by default). The 0x80-0xF6 command set belongs to the first generation UartTFT, not to this engine.
- Chip marking (photo): HFD168BDP; Stream Deck core (button events, variable writes, page switch) works with the stock engine; dynamic icon replacement at runtime is not documented.

## 2026-11-20 - UI_Editor-II manual pages 48-303 (official): control, icon and host mechanisms
- Touch to host: Button/Popup/Variable Button/Multi-Variable Button have reportToHost (off by default); frame 5A A5 07 41 FF FF <returnValue> <CRC>; no separate press and release events (pressedIcon is appearance only). Multi-Variable Button writes up to 8 variables and can change page.
- Host to screen: variable addresses 0x0000-0x1FFF (LT168A/B, 16 KB, 2 bytes per address; LT7689 0x0000-0x5FFF); text, number and icon controls follow variable values; string controls up to 2 KB.
- Host presses a button: write the _triggerValue (0x0001-0xFFFF, unique per page) to register 0x700D; only Button, Popupbox, Variable Button, Multi-Variable Button, number/Chinese/English keyboard support it; with hostControl enabled the control stops reacting to touch and is not drawn (copy the control to keep touch).
- Icons: no runtime download of new images; icon IDs refer to assets packed in UartTFT-II_Flash.bin; dynamic icon change = choose among preloaded images by variable value.
- Register table for LT168A/B (p.303): 0x7000 page, 0x7001 backlight, 0x7002-0x7007 time, 0x7008 time confirm, 0x700A WAV, 0x700B volume, 0x700C resistive calibration, 0x700D key code trigger, 0x700E auto backlight, 0x700F sleep brightness, 0x7010 sleep time, 0x7011 serial upgrade, 0x703F language.
- The slide menu (sliding select) widget works only on LT168 RGB screens, not on LT168B MCU screens (p.117).

## 2026-11-20 - UI update route in the manual (Flash_RW-II over USB Vcom)
- Manual p.250: "Update UI project with Flash_RW-II": open the com port, Input Bin, update; limit: only UartTFT-II_Flash.bin, not Mcu_Code.bin. p.247-249: requires an Mcu_Code.bin that supports reading and writing the external SPI Flash and MCU Flash over Uart/Vcom/HID. p.281: UI_Debugger-II sends 10 70 11 AA 55 (full frame 5A A5 ...) to enter serial upgrade, then Update MCU / Update Flash. p.221-222: HID/Vcom need the matching Mcu_Code (module_select.h switches).
- Flash_RW-II is not in the extracted UI_Editor-II_V3.20 folder; whether the unit's V2.2 Mcu_Code accepts it is unverified (the stock parsers do have 0x61-0x67 flash commands). hidDeviceID.ini lists EEEF PID 2929/1616/1617/1618 for the HID mode; the unit (EEEF:268A, CDC) must use the Uart tab.
- Correction: lastbin_path.ini holds a project folder path of the vendor developer (user 13781), not a bin file; the earlier inference "UI_Debugger remembers a bin" is withdrawn.

## 2026-11-20 - manual p.245-251, p.276-284: serial UI update procedure
- p.250 UI project update over serial: (1) send 5A A5 07 10 7042 0001 9E D7 (screen enters receive mode, close the serial tool), (2) Flash_RW-II: Open Com Port, Input Bin, (3) Write Addr 0, target SPI Flash, Write, (4) send 5A A5 07 10 7042 0000 5F 17 to return to normal. Limit: only UartTFT-II_Flash.bin, not Mcu_Code.bin. CRC-16/MODBUS verified on both frames (D79E and 175F, low byte first).
- Flash_RW-II (p.245-246): read up to 2 KB, check = CRC-32 of a range, write from a bin file at an address, target MCU Flash or SPI Flash; needs Mcu_Code with Uart/Vcom/HID flash read/write (module_select.h UARTBUS_OPTION 0/4/3).
- p.281-284: 10 70 11 AA 55 enters the bootloader serial update, then LT_Uart_GUI updates Mcu_Code and Flash (this tool writes MCU code); Flash.ini example W25N01GV 0xEFAA21 65536 2048 matches the unit's flash.
- Unverified for the unit: 0x7042 handling in V2.2, protocol equality of Flash_RW-II with the stock 0x61-0x65 commands, availability of Flash_RW-II (not in the downloaded package).

## 2026-11-20 - LT268x/269 update manual pages 3-6: LT_VCOM_GUI
- Levetop update flow (LT268x/269 manual): the bootloader is programmed at the factory; MCU_Code.bin (internal flash) and UartTFT_Flash.bin (external SPI flash) are updated with LT_VCOM_GUI (USB virtual serial) or LT_Uart_UI (UART), SD card (UartTFT_Flash only) or USB stick. LT_VCOM_GUI has Input File for both files, Update All / Update MCU / Update Flash, Check Mcu CRC, Flash Info, Check Flash CRC, Erase whole flash, Run Uart Application.
- Entering update mode: pull the BUSY pin low, then connect USB; leaving: Run Uart Application or RST (the tool then no longer sees the port). This matches the unit's behaviour (FN X 0 6 puts the screen into the bootloader, only a power cycle returns): the keyboard most likely drives a BUSY-like line of the screen (INFERENCE).
- Flash info shown by the tool (example): FlashID 0xef4018, size 16777216, name W25Q128FV; the unit would show 0xefaa21, 134217728, W25N01GV.
- This is the LT268 family manual; compatibility of LT_VCOM_GUI with the unit's bootloader (id 0x1971168B) is unverified.

## 2026-11-20 - UI image compatibility check (aula_ui_compat.py, offline)
- Factory UI image (127599044 bytes, sha256 4cb3fa5c...): L = 10704364, CRC rule MATCH, config 320x480, editor strings V2.30 / V2.20 at 0xA4 / 0xB0.
- Levetop demo (LT168B Four In One 480x272 V3.10, 70751298 bytes): L = file size, CRC rule MATCH, config 480x272, strings V3.10000 / V1.00000; extra fields at 0x94-0x9F (zero in the factory image).
- Same family: identical table 0xC2-0x16B and font index from 0x180. The unit's UI was compiled with UI_Editor-II V2.30; a V2.30 editor exists in the SDK (UI_Editor-II_V3.20\platforms\UI_Editor-II_V2.3020240116-1.exe, 3772928 bytes, not yet run). Plan: compile the minimal UI with V2.30 to match the format.

## 2026-11-20 Screen UI bin format findings
- UI_Editor-II V2.30 test builds (320x480): A_blank 0x21DE8, B_button 0x21DFC, C_button_tx 0x21DFC.
- Header: 0x8C magic 5A A5 06 00, 0x90 = 320x480, 0xA4 editor ver, 0xB0 project ver, 0x174 = total image length (verified on 5 files).
- 16-byte integrity field at 0x16C-0x173 + 0x178-0x17F; not plain MD5. Always build via UI_Editor; never hex-patch.
- Button record 19 bytes; flags byte bit6 (0x40) = serial return enable; X1,Y1,X2,Y2,return value LE16.
- Official UartTFT-II_Flashl99.bin (evbunpack of Screen reset firmware.exe), 127,599,044 bytes:
  img1 @0x0 (0xA355EC), zero fill to ~0x3E355EC, data ~0x3E355EC-0x5B10000, img2/3/4 identical (SHA256 62BA430E...) @0x5B10000/0x65455EC/0x6F7ABD8.
- Status: no flash performed.
- Official bin data region starts exactly at 0x4000000 (64 MiB): records of [u32 len=0x4B000][u16 w=320][u16 h=480][RGB565], ~92 frames est. No GIF/PNG/JPEG/RIFF signatures; BM hits likely false positives.
- img1 vs img2: only header (22 bytes) and +0x30 section (0x622A84, 569 entries) to end differ; pages/touch identical. Baseline = img1 @0x0 (assumed active).
- ISP payload (evbunpack of L99_ISP_CNUI_V1.23_156): UartTFT-II_Flash.bin 0x5B0D07C (sha256 903A4FBA...) = img2 + zero fill to 0x4000000 + resource region identical to full official bin (tail zeros trimmed). Verified.
- ISP folder also contains Flash.ini (JEDEC table: id, page size, page count), HFD_Code_V2.2.bin (A...0x4AA88), HFD_Code_V2.3.bin (0x4C934), HFD_ISP_TOOL_V1.31.exe. Tool strings reference relative /Flash.ini, /UartTFT-II_Flash.bin, /HFD_Code_V2.x.bin, size check vs flash IC, and FileCRC/FlashCRC verify.
- Inference: screen flash >=128 MiB, likely 1 Gbit SPI NAND. Plan: stage 0 composite bin (custom UI + official resource region), stage 1 reflash official bin via unpacked tool with Procmon, stage 2 custom flash.
- Status: no flash performed.
- Stage 0 composite built: isp_stage\custom_c\UartTFT-II_Flash.bin size 0x5B0D07C, sha256 3B27223F7AAD8CB5E77F578A3825C48EE5892AACD272F3117237EB1EB83EFB4A. Image 0x0-0x21DFC = C_button_tx (7A793941...), zero fill to 0x4000000, resource region identical to official. isp_stage\official verified (903A4FBA...).
- Status: no flash performed.
- REA boot_safety_v2 static: custom_c has 1 page (no page 29), varinit 0x11DD0 all zero vs 34 non-zero bytes in official, other sections empty. custom_c confirmed NOT flash-safe. HFD_Code_V2.2 refs: 0x6000F000 @0x2504B, 0xAA55 @0x1416/0x14D6 (early code, possible pre-UI update check, unverified). Emulator build failed (missing libc6-dev); rerun after build-essential.
- REA boot_safety_v2 emulator (kei825 cemu, stock HFD_Code_V2.2): both official and custom_c NAND boot without halt, answer UART (33 70 00 00 00, read 0x7000). custom_c ignores page 1 (stays page 0). 0x7011=0xAA55 sets 0x6000F000 0->FFFFFFFF and jumps to bootloader 0x60000100 for BOTH -> update mode reachable regardless of UI content (emulator evidence, not hardware-verified).
- custom_c still not flashed: low test value (no page 1). Next: choose 30-page UI_Editor project (stock HFD) or kei825 custom HFD firmware route.

## 2026-11-22 - A2-R7-H5 Visible Resource and Touch Integration

### Summary
- Completed A2-R7-H5 offline integration validation.
- Confirmed that one modified UI/NAND image can produce both a visible framebuffer change and a modified UART touch event.
- Acceptance status: PASS_VISIBLE_RESOURCE_AND_TOUCH.
- Evidence classification: VERIFIED OFFLINE.

### Verified Results
- Target: Page 21 Mini Numpad.
- Resource: Bank 0, ID 21.
- Resource address: 6624228.
- Resource size: 338 bytes.
- Resource dimensions: 13x13.
- Resource format: 2.
- Reproducible framebuffer change: 5 pixels.
- Changed region: (256,14)-(261,15).
- Touch record offset: 150602.
- Touch center: (198,440).
- Original UART event: 0x40.
- Modified UART event: 0x41.
- Page remained 21 after touch.
- Original UI/NAND image preserved.

### Candidate Image
SHA-256:
66c276756646a642e28e082ae53cfcb5d67689295388c5cb27060a9eb3d291e0

### Limitations
- The visible resource change affects the upper status area.
- The modified resource has not been proven to belong to the selected button icon.
- Arbitrary custom icon generation remains unresolved.
- Custom 4x4 UI/NAND image generation remains incomplete.
- Physical USB integration remains unverified.
- Physical custom flashing remains NO-GO.

### Next Task
A2-R7-H6: Visible Button Icon Replacement.

Objective:
Replace one existing Page 21 Mini Numpad button icon with
a custom image while preserving touch UART behavior and
Home navigation.

Required acceptance:
- Custom icon visibly rendered in stock CEmu.
- Correct button touch UART event.
- Home navigation preserved.
- Deterministic image integrity validation.
- No physical hardware writes.

