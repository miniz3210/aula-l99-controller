# Changelog

## Unreleased

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