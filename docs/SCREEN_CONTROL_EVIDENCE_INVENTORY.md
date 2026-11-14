# AULA L99 USB-Only Screen-Control Evidence Inventory

**Repository:** `C:\temp\aula-l99-controller`
**Accepted checkpoint:** `13b1ff06d99c837a1c2690ae897f84d27a51db66`
**Mode:** BOUNDED DOCUMENTATION
**Token target:** < 8K (hard stop 12K)

---

## 1. Verified USB Device Interfaces

| Interface | VID:PID | Transport | Evidence Source | Classification |
|-----------|---------|-----------|-----------------|----------------|
| Keyboard HID | 0x0C45:0x800A (MI_00) | USB HID (Raw Input) | `src/aula_bridge/devices.py:62-63`, `scripts/list_aula_hid.py:3-4`, `aula_home_numpad_transition.pcapng` | **A. User-unit verified** |
| Screen CDC/Serial | 0xEEEF:0x268A | USB CDC (virtual COM) | `README.md:59-61`, `PROJECT_HANDOVER.md:31-32`, `aula_home_numpad_transition.pcapng` | **A. User-unit verified** |

**USB Attribution Evidence (`aula_home_numpad_transition.pcapng`):**
- Capture SHA256: `B4DAD6E13612C615F3A03400BCC9EED8F98F6D02E0B256368B8E82C3C608F5EE`
- **Device 6:** VID:PID 05E3:0626 (Genesys Logic USB Hub)
- **Device 13:** VID:PID 1A86:8091 (Touch/pointer)
- **Device 15:** VID:PID EEEF:268A (Screen CDC)
- **Device 16:** VID:PID 0C45:800A (Keyboard HID)

**Important:** USB device addresses (e.g., Device 6, 13, 15, 16) are capture-local and must not be generalized across different captures.

**Key evidence:**
- Keyboard side: Raw Input enumeration confirms VID 0C45 / PID 800A on MI_00 (`src/aula_bridge/devices.py:81-94`). Physical keyboard and screen Mini Numpad share MI_00; distinguishable only by make-code + E0/flags, not device handle (`src/aula_bridge/devices.py:85-88`).
- Screen side: Windows CDC/serial interface exposed as COM port; VID EEEF / PID 268A confirmed via device enumeration and official updater string references (`README.md:59-61`, `CONTROLLED_FLASH_PLAN.md:124`).
- Keyboard events and screen runtime updates use **different transport paths** (`README.md:66`, `PROJECT_HANDOVER.md:38`).

---

## 2. Verified Image Upload Behavior

| Property | Value | Evidence Source | Classification |
|----------|-------|-----------------|----------------|
| Protocol chunks | 154 logical chunks (150 data + 4 short commands) | `README.md:139-142`, `scripts/replay_captured_screen.py:12-14` | **A. User-unit verified** (capture) |
| Data packet size | 2060 bytes | `README.md:140`, `scripts/replay_captured_screen.py:12` | **A. User-unit verified** |
| Total captured stream | ~309,071 bytes | `README.md:142` | **A. User-unit verified** |
| Payload format | Not standard JPEG | `README.md:143`, `scripts/decode_captured_frame.py:94-104` | **A. User-unit verified** |
| Upload target | Photo/background/GIF flash slots | `README.md:145`, `CONTROLLED_FLASH_PLAN.md:143` | **A. User-unit verified** |
| Overlays Mini Numpad | No — separate path | `README.md:145-146`, `CONTROLLED_FLASH_PLAN.md:107` | **A. User-unit verified** |
| ACK behavior | Screen acknowledges packets; ACK ≠ address safety | `README.md:146-147`, `README.md:149-150` | **A. User-unit verified** |
| Official app speed | ~1.205 s (150 × 2060-byte USB Bulk OUT) | `README.md:155-158` | **B. Vendor artifact verified** |
| Python replay speed | 41.6 s (stable) / 67.7 s (baseline) | `README.md:159-162` | **A. User-unit verified** |

**Critical limitations:**
- Current Python replay splits 2060-byte packets into ~33 × 64-byte pyserial writes with artificial pacing (`README.md:163-166`).
- 115200 CDC line-coding is **not** the physical throughput limit for USB bulk (`README.md:167`).
- Next milestone: Win32 overlapped I/O uploader (`scripts/replay_captured_screen_win32.py` planned, not implemented).

---

## 3. Runtime RAM Protocol Evidence

| Aspect | Status | Evidence Source | Classification |
|--------|--------|-----------------|----------------|
| Short runtime frame codec | Documented offline implementation | `scripts/research/l99_runtime_frame_codec.py:6-17` | **C. Levetop reference** (third-party protocol doc) |
| Frame format | `5A A5 | length:u8 | body | CRC16:LE16` | `scripts/research/l99_runtime_frame_codec.py:7-9` | **C. Levetop reference** |
| Read opcode | `0x03 | word_address:BE16 | word_count:BE16` | `scripts/research/l99_runtime_frame_codec.py:11` | **C. Levetop reference** |
| Write opcode | `0x10 | word_address:BE16 | word_0:BE16 ...` | `scripts/research/l99_runtime_frame_codec.py:12` | **C. Levetop reference** |
| Address range | 0x0000–0xFFFF (16-bit word indices) | `scripts/research/l99_runtime_frame_codec.py:14` | **C. Levetop reference** |
| Max read words | 8 per chunk | `scripts/research/l99_runtime_frame_codec.py:15` | **C. Levetop reference** |
| CRC algorithm | CRC16/MODBUS (poly 0xA001, init 0xFFFF) | `scripts/research/l99_runtime_frame_codec.py:78-92` | **C. Levetop reference** |
| **User-unit live capture** | **NOT captured** — only third-party documentation | `scripts/research/l99_runtime_frame_codec.py:3-5` | **UNVERIFIED on user unit** |

**Status:** The short runtime frame codec is implemented from third-party protocol documentation (Levetop/UartTFT reference). **No user-unit USB capture of live RAM read/write frames exists in this repository.** The codec passes offline round-trip tests but has not been validated against the user's hardware.

---

## 4. Touch Event Transport

| Path | Mechanism | Evidence Source | Classification |
|------|-----------|-----------------|----------------|
| Screen Mini Numpad → PC | USB HID via keyboard controller (VID 0C45:800A MI_00) | `src/aula_bridge/devices.py:13-15`, `aula_input_bridge.py:3-5` | **A. User-unit verified** |
| Touch return codes | 17 action codes (0x0030–0x0040) + Home (0x0020) | `README.md:114-132`, `scripts/inspect_l99_descriptor.py:179-219` | **A. User-unit verified** |
| Touch record parsing | Type 0xC001 (action), 0x8001 (navigation) | `scripts/inspect_l99_descriptor.py:205-214` | **A. User-unit verified** |
| Rectangle mapping | Verified per-button [x1,y1,x2,y2] | `README.md:114-132` | **A. User-unit verified** |
| Raw touch coordinates | Captured via `scripts/analyze_touch_candidates.py` (11-byte packets) | `scripts/analyze_touch_candidates.py:38-47` | **A. User-unit verified** (capture) |
| HID Feature Report (telemetry) | 64-byte report on Interface 3 (SET_REPORT wValue 0x0300) | `PROJECT_HANDOVER.md:27-28` | **A. User-unit verified** |

**Key finding:** Screen touch events are forwarded through the keyboard HID interface (VID 0C45:800A), not the screen CDC interface. The bridge uses Raw Input to attribute events to the L99 device and maps verified Mini Numpad return codes to logical keys.

---

## 5. Runtime Display-Update Limitations

| Limitation | Evidence | Classification |
|------------|----------|----------------|
| **No live framebuffer RAM write verified** | Photo upload targets flash slots, not live LCD | `README.md:145`, `CONTROLLED_FLASH_PLAN.md:107` |
| **No verified visible LCD update** | No visible LCD update caused by runtime RAM writes has been verified on the user's AULA L99. | **Project policy** |
| Image upload ≠ live display update | Upload path is photo/background/GIF flash regions | `README.md:145` |
| Offline descriptor patch only | `scripts/patch_l99_numpad_icon.py` patches flash image only | `README.md:230-246` |
| No runtime icon-switch protocol verified | Type 3 variable-to-icon dispatcher **UNVERIFIED** | `README.md:21`, `PROJECT_HANDOVER.md:27` |
| Type 3 runtime mapping | Native Type 3 dispatcher **NOT verified** | `README.md:21`, `PROJECT_HANDOVER.md:27` |
| Type 5 animation control | Animation groups (3) and frames (134/171) are separate structures | `scripts/type3_inventory.py:243-258` |

**Critical distinction:** The verified photo upload (154 chunks, ~309 KB) writes to **flash storage** for photo/background/GIF slots. It does **not** overlay the active Mini Numpad page (Page 21) and is not a live framebuffer path.

---

## 6. Page-Switch Evidence Status

| Claim | Status | Evidence |
|-------|--------|----------|
| Page 21 = Mini Numpad | **VERIFIED** | `README.md:12`, `scripts/inspect_l99_descriptor.py:528-574` |
| Page 21 touch records (18) | **VERIFIED** | `README.md:110`, `PROJECT_HANDOVER.md:102` |
| 0x7000 system page switching | **NOT VERIFIED** — Levetop reference only | `README.md:368`, `docs/THIRD_PARTY_REFERENCES.md:7` |
| Widget WriteAddr operations | **NOT VERIFIED** — Levetop reference only | `README.md:368` |
| Official example ≥ 90 pages | **NOT VERIFIED** — Levetop reference only | `README.md:376` |
| Page table structure | **VERIFIED** (30 pages, 12-byte records) | `PROJECT_HANDOVER.md:629-633` |

**Classification:** Page 21 structure and Mini Numpad mapping are **A. User-unit verified**. System page switching via 0x7000, WriteAddr operations, and ≥90-page support are **C. Levetop official reference** claims — not reproduced on the user's unit.

---

## 7. GT911 Evidence Status

| Claim | Status | Evidence |
|-------|--------|----------|
| GT911 touch controller on user's unit | **NOT VERIFIED** | `README.md:384-387` |
| Public teardown shows GT911 | **D. Public teardown evidence** (not user's unit) | `README.md:380-384` |
| User's unit physically opened | **No** | `README.md:385` |

**Classification:** GT911 is **D. Public teardown evidence** from a third-party teardown sample. **Do not claim GT911 is installed on the user's unit.** The user's unit has not been physically opened.

---

## 8. LT168 / LT268 Identity Uncertainty

| Identifier | Source | Status |
|------------|--------|--------|
| HFD168BDP (screen controller) | Public teardown | **D. Public teardown** — not user's unit |
| LT168-family controller firmware | README / Handover | **STRONG_INFERENCE** — firmware compatibility only |
| LT268A / LT2686 UartTFT | `PROJECT_HANDOVER.md:446` | **Under investigation** |
| Levetop LT168B SDK / UI_Editor-II | `README.md:376` | **C. Levetop reference** |
| Exact silicon identity of user's unit | `README.md:386-387` | **UNVERIFIED** |

**Key statement from README.md:386-387:**
> "The user's firmware/resource artifacts show strong compatibility with the Levetop LT168/UartTFT ecosystem. Exact silicon identity and hardware revision of the user's unit remain unverified."

**Do not state:** User's unit contains HFD168BDP; HFD168BDP = LT168B; flash = W25N01GV; panel = ST7796S.

---

## 9. Known Hardware Safety Restrictions

| Restriction | Source | Enforcement |
|-------------|--------|-------------|
| **HARDWARE WRITE STATUS: NO-GO** | `README.md:180`, `CONTROLLED_FLASH_PLAN.md:327` | Hard block |
| No unknown flash addresses | `README.md:195` | Policy |
| No force mode | `README.md:196` | Policy |
| No arbitrary erase/write replay | `README.md:197` | Policy |
| No firmware update during extraction | `README.md:198` | Policy |
| No claim of universal brick recovery | `README.md:199` | Policy |
| Official reset package ≠ raw NAND dump | `README.md:200-201`, `CONTROLLED_FLASH_PLAN.md:265-266` | Verified |
| No per-device OOB/ECC/bad-block/calibration data | `README.md:201`, `CONTROLLED_FLASH_PLAN.md:266` | Verified |
| About-page V1.31 source unresolved | `README.md:202`, `PROJECT_HANDOVER.md:180-188` | Verified |
| Original vendor images = immutable references | `README.md:193` | Policy |
| ACK ≠ address safety | `README.md:149-150` | Verified |
| Image-level self-checksum = UNKNOWN | `README.md:186`, `docs/UI_IMAGE_CHECKSUM_MODEL.md:39-40` | Blocker |

**Critical blockers for GO decision** (`CONTROLLED_FLASH_PLAN.md:337-340`):
1. Image-level self-checksum requirement (per-packet CRC verified; image-level UNKNOWN)
2. UI-only vs combined HFD write scope (STRONG_INFERENCE only; exact UI-only construction NOT verified)
3. Recovery behavior after interrupted write (UNKNOWN; residual brick risk explicit)

---

## 10. Open Feasibility Questions

| # | Question | Current Status | Evidence Needed |
|---|----------|----------------|-----------------|
| 1 | Does live RAM write update LCD? | **UNVERIFIED** — claimed impossible by project policy | User-unit USB capture of short runtime write frames + screen observation |
| 2 | Is 0x7000 page switching real on user unit? | **C. Levetop reference only** | Live capture of page-switch command + screen observation |
| 3 | Can Type 3 widgets switch icons at runtime? | **NOT VERIFIED** (dispatcher unknown) | HFD Code V2.3 disassembly of Type 3 handler; live variable write test |
| 4 | Does GT911 exist on user's unit? | **D. Teardown only** | Physical teardown or vendor datasheet for user's revision |
| 5 | What is exact screen controller silicon? | **UNVERIFIED** | Physical teardown or firmware query via ISP |
| 6 | Is image-level self-checksum in UartTFT-II_Flash.bin? | **UNKNOWN** (scanner found no match) | `scripts/flash_checksum_scanner.py` deep scan + HFD Code analysis |
| 7 | Exact UI-only package acceptance by updater? | **STRONG_INFERENCE** | Official update capture (Procmon + USBPcap) |
| 8 | Interrupted-write recovery behavior? | **UNKNOWN** | Official update capture + power-loss test (requires hardware) |
| 9 | Can photo upload path be repurposed for live updates? | **NO** — separate flash path | Verified: upload targets flash slots, not live page |
| 10 | Short runtime protocol (5A A5 / CRC16) functional on user unit? | **C. Levetop ref only** | Live USB capture of 5A A5 frames during widget interaction |

---

## 11. Recommended Evidence for Next USB-Only Screen-Control Milestone

| Priority | Evidence Needed | Method | Repository Artifacts to Produce |
|----------|-----------------|--------|--------------------------------|
| **P1** | Live capture of short runtime frames (5A A5) during native widget interaction | USB capture (USBPcap) + screen recording while using official AULA software | `screen_runtime_capture.pcapng`, `runtime_frame_log.json` |
| **P1** | Verify Type 3 variable addresses & icon-selection formula | HFD Code V2.3 disassembly (bounded CFG) + live RAM read via short runtime protocol | `type3_dispatcher_analysis.md`, `variable_address_map.json` |
| **P2** | Official L99 ISP V1.23.exe update capture (answers 10 static-analysis questions) | Procmon + USBPcap + screen recording (per `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md`) | `official_capture_report.json`, `procmon_filters.json` |
| **P2** | Image-level self-checksum resolution | `scripts/flash_checksum_scanner.py --mode deep` + HFD Code checksum handler analysis | `checksum_scan_report.json`, `checksum_handler_disassembly.md` |
| **P3** | Win32 overlapped I/O uploader for 2060-byte packets | Implement `scripts/replay_captured_screen_win32.py` per `README.md:169-176` | `replay_captured_screen_win32.py`, benchmark results |
| **P3** | Physical teardown (if user permits) | Document silk-screen markings, controller ICs, flash part number | `teardown_report.md` (local only) |
| **P3** | Type 5 animation control protocol | Disassembly of animation handler + live frame capture | `type5_animation_protocol.md` |

**Milestone gate:** USB-only screen control requires **P1** (live runtime frame capture + Type 3 dispatcher verification). Without verified RAM write → LCD update path, all screen-control work remains flash-image patching only (offline, NO-GO for hardware write).

---

## A. Created File

`docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md` — this document.

---

## B. Evidence Sources (Repository Paths)

| Category | Key Files |
|----------|-----------|
| USB device interfaces | `src/aula_bridge/devices.py`, `scripts/list_aula_hid.py`, `aula_input_bridge.py`, `aula_home_numpad_transition.pcapng` |
| Image upload behavior | `scripts/replay_captured_screen.py`, `scripts/decode_captured_frame.py`, `scripts/extract_raw_usb_payloads.py`, `scripts/push_solid_color.py` |
| Runtime RAM protocol | `scripts/research/l99_runtime_frame_codec.py` |
| Touch events | `scripts/analyze_touch_candidates.py`, `scripts/inspect_l99_descriptor.py` (parse_touch_records) |
| Factory UI / descriptors | `scripts/inspect_l99_descriptor.py`, `scripts/patch_l99_numpad_icon.py`, `scripts/type3_inventory.py` |
| Firmware provenance | `docs/VENDOR_FIRMWARE_PROVENANCE.md`, `docs/FIRMWARE_PACKAGE_MAP.md` |
| Flash/ISP analysis | `docs/CONTROLLED_FLASH_PLAN.md`, `docs/RECOVERY_COMPATIBILITY_MATRIX.md`, `docs/UI_ONLY_PACKAGE_CONSTRUCTION.md` |
| Checksum model | `docs/UI_IMAGE_CHECKSUM_MODEL.md`, `scripts/flash_checksum_scanner.py` |
| Official capture plan | `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md`, `scripts/analyse_official_capture.py` |
| M*Core CFG / JMPI | `scripts/research/hfd_cfg.py`, `scripts/research/mcore_literal_pool.py`, `scripts/research/jmpi_evidence_postprocess.py` |
| Third-party references | `docs/THIRD_PARTY_REFERENCES.md`, `docs/PROJECT_HANDOVER.md` |

---

## C. Unresolved Questions (Critical for USB-Only Screen Control)

1. **Live RAM write → LCD update path:** No user-unit evidence exists. Short runtime protocol (5A A5) is documented from Levetop references only. **Must capture live frames during native widget operation.**
2. **Type 3 runtime dispatcher:** Native variable-to-icon selection logic in HFD Code V2.3 is **NOT verified**. Bounded CFG exists but Type 3 handler not located.
3. **Image-level self-checksum:** `scripts/flash_checksum_scanner.py` scanned all fixed-structure regions with 6 algorithms — **NO_MATCH**. Status: UNKNOWN (not proof of absence).
4. **Exact UI-only package acceptance:** ISP tools reference all 3 files (UI + HFD V2.2 + HFD V2.3). Softce confirms UI-only packages existed, but exact accepted construction **NOT verified** by static analysis.
5. **Interrupted-write recovery:** No explicit recovery path in static analysis. Manual re-entry STRONG_INFERENCE (one config); automatic UNKNOWN. Residual brick risk explicit.
6. **Screen controller silicon identity:** User's unit unopened. Public teardown shows HFD168BDP + GT911 — **not verified for user's revision**.

---

## D. Git Status

```bash
$ git status
# On branch main
# HEAD: 13b1ff06d99c837a1c2690ae897f84d27a51db66 (accepted checkpoint)
# Working tree: clean (no modifications to tracked files)
# New file: docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md (this file, untracked)
# No staged changes
# No commits created
```

**Policy compliance:** No code/tests modified. No USB hardware accessed. No commit/tag/push/version bump. Only new file created at allowed path.

---

**End of Evidence Inventory**