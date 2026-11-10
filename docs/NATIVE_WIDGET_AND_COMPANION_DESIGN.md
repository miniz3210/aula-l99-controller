# Native Widget and Companion Design Report

**Project:** AULA L99 Controller  
**Branch:** main  
**Date:** 2026-11-10  
**Status:** Read-only design report. No firmware, source, script, binary, or manifest modified.

---

## 1. Executive summary

This report covers four analysis areas for the AULA L99 touchscreen controller: native type 3/type 5 dynamic-widget findings, Page 21 icon candidates for runtime feedback, hold-press menu-switching approaches (PC bridge vs. native), and a firmware-free Bitfocus Companion input-only proof-of-concept design. All findings are read-only and derived from existing documentation and the softce inspection manifest. No hardware access, USB/HID/COM writes, flashing, or updater execution was performed.

Key conclusion: Page 21 already has a variable-15 type 3 dynamic-widget record, making it a candidate for native runtime-feedback without changing touch records. PC-side hold detection is feasible via a deterministic state machine but limited by WH_KEYBOARD_LL source identification. Native L99 hold behavior is UNVERIFIED. The Companion POC is a Windows bridge translating 17 logical HID keys into Companion local API/Satellite calls.

---

## 2. Verified dynamic-widget findings

**A. Type 3 records (VERIFIED)**

- 310 type 3 records across 28 pages (manifest stats).
- Each type 3 record is 14 bytes with fields: `variable`, `x`, `y`, `first_icon`, `last_icon`, `min_value`, `max_value`.
- Parsed from manifest payload (LE16 fields): variable (u16), x (u16), y (u16), first_icon (u16), last_icon (u16), min_value (u16), max_value (u16).
- Page 21 contains one variable-15 type 3 record at manifest offset 150412, payload `0f0071002a003e01ffff00000000`, x=113, y=42, first_icon=318, last_icon=65535, min_value=0, max_value=0.
- Page 21 page record at offset 0x00021ECC; display block `[0x00024B7E, 0x00024C4A)` (204 bytes); touch block `[0x00024C4A, 0x00024DA0)` (342 bytes).

**B. Type 5 records (VERIFIED)**

- Five type 5 records found:
  - Page 5: variable 31, x=152, y=358, w=28, h=28, first_animation=1
  - Page 5: variable 27, x=153, y=292, w=28, h=28, first_animation=1
  - Page 5: variable 23, x=153, y=227, w=28, h=28, first_animation=1
  - Page 5: variable 19, x=152, y=161, w=28, h=28, first_animation=1
  - Page 25: variable 784, x=60, y=173, w=200, h=113, first_animation=2
- Three animation groups referenced: group 0 (page 0), group 1 (page 5), group 2 (page 25).
- Manifest stats: 3 animations, 134 animation frames.

**C. Runtime frame and RAM block (VERIFIED)**

- Softce `protocol.md` §5: short runtime frame `5A A5 | length:u8 | body | CRC16(body):LE16`, length = len(body) + 2, CRC16 reflected polynomial 0xA001 init 0xFFFF.
- Read body: `03 | word_address:BE16 | word_count:BE16`. Write body: `10 | word_address:BE16 | word_0:BE16 | ...`.
- RAM block `0x0600..0x0637` verified with word addresses:
  - `0x0600` Current PV power
  - `0x0608` Grid power
  - `0x0610` Battery charge
  - `0x0618` Floor temperature
  - `0x0620` Daily PV energy
  - `0x0628` Daily grid import
  - `0x0630` Status / last-update time
  - `0x0638..0x0639` Signature words `0x454E, 0x4531` ("ENE1")
- Each text field occupies eight words (16 bytes), ASCII at most 15 bytes zero-padded to 16. Seven fields total 56 words.
- This channel updates runtime RAM; it is not ISP flashing.

---

## 3. Hypotheses and unknowns

| Item | Status | Detail |
|------|--------|--------|
| Widget variable N → RAM word `0x0600+N` mapping | UNVERIFIED | No evidence that type 3 `variable` field maps to RAM word index `0x0600+N`. The `variable` field may be an internal widget ID unrelated to the `0x0600` RAM block. |
| Type 5 timing/start/stop/loop semantics | UNVERIFIED | `first_animation` field exists but animation start/stop/trigger/loop behavior is not documented in manifest or protocol.md. |
| Type 3 icon-range selection behavior | UNVERIFIED | How `first_icon`/`last_icon`/`min_value`/`max_value` select icons at runtime is not established. |
| Existing pages demonstrating runtime icon switching | UNVERIFIED | No page in manifest demonstrates a type 3 record changing its displayed icon based on a variable value at runtime. |
| Reusable volatile RAM variable on Page 21 | UNVERIFIED | Variable 15 exists on Page 21 but its runtime writability and semantic meaning are unknown. |
| Companion feedback mapped to native icon states | UNVERIFIED | No mapping between Companion state and native widget variables established. |

---

## 4. Ranked icon candidates (corrected)

Criteria: runs of ≥4 consecutive icon IDs, unreferenced by expanded type 3 ranges and all touch/other decoded display references, decode successfully in both banks with matching dimensions/format/usable payload, no payload overlap, no aliasing of referenced-icon payloads, not overlapping another known payload, suitable for normal/active/warning/disabled states.

**Why icons 15–19 were rejected.** Page 1 contains a valid type 3 record with first_icon=14, last_icon=20, min_value=0, max_value=6 (manifest offset 149442, payload `080015010b000e00140000000600`). Because first_icon != 0xFFFF, last_icon != 0xFFFF, and last_icon >= first_icon, every icon ID from 14 through 20 (inclusive) is treated as referenced by that range. Icons 15–19 therefore fall inside an expanded referenced range and cannot be candidate runs.

**Recalculation method.** Every valid type 3 range was expanded inclusively from first_icon through last_icon. Fixed first_icon/last_icon values, touch-record unpressed/pressed icons, and all other decoded display record icon references were added. Animation frame references were tracked separately. Aliases/shared payloads were checked via icon-table address equality across banks and IDs.

Expanded type 3 ranges include [14–20] (pages 1–5, 8–15, 17–23), [1–2], [3–4], [5–6], [7–8], [9–13], [80–83] (page 5), [86–87] (page 5), [89–90] (page 8), [92–94] (pages 9–10), [198–199] (page 13), [102–103] (page 14), plus single-value references for type 3 records where first_icon or last_icon is 0xFFFF. Touch-record references cover icons 208–209, 319–352, and 400–435.

All 569 icon IDs were checked against manifest decode status in both banks (0 and 1). A run qualifies only if every ID decodes with status `decoded` in both banks with identical width/height/format, is absent from all expanded ranges and touch references, and its payload allocation does not overlap any referenced-icon payload or another run payload.

**Corrected candidate runs (all verified safe):**

| Rank | Icon IDs | Count | Dimensions | Format | Bank 0 desc offset | Bank 1 desc offset | Payload bank 0 | Payload bank 1 | Shared/aliased | Resource conflicts | Confidence |
|------|----------|-------|------------|--------|--------------------|--------------------|----------------|----------------|----------------|--------------------|------------|
| 1 | 30–43 | 14 | 11 x 17 | 2 (ARGB4444) | 0x006232F4 + id×12 | 0x00624DB4 + id×12 | 0x6624566..0x6627932 | 0x6624566..0x6627932 | No | None known | VERIFIED |
| 2 | 260–269 | 10 | 10 x 13 | 2 (ARGB4444) | 0x0062439C + id×12 | 0x0062622C + id×12 | 0x6689B92..0x668B592 | 0x6689B92..0x668B592 | No | None known | VERIFIED |
| 3 | 280–289 | 10 | 14 x 20 | 2 (ARGB4444) | 0x00624404 + id×12 | 0x00626294 + id×12 | 0x668D532..0x668E7E6 | 0x668D532..0x668E7E6 | No | None known | VERIFIED |

Other unreferenced consecutive runs (22–63, 129–134, 212–253, 255–309, 314–317, 355–399, 436–550, 555–559) were rejected: each contains at least one icon that fails to decode in both banks, has inconsistent dimensions/format across banks, is an invalid_bounds/empty_or_nonbitmap entry, or overlaps referenced payloads.

Descriptor bank bases (VERIFIED): bank 0 at 0x00622A84, bank 1 at 0x00624530, 12 bytes per descriptor, 569 per bank.  
Descriptor offset formula: `bank_base + icon_id × 12`.

**Best icon candidate:** Icons 30–43 (rank 1), a 14-ID consecutive run decoding identically in both banks at 11×17 format 2 (ARGB4444), absent from all expanded icon ranges and touch references, with distinct bounded non-overlapping payload allocations and no aliasing of referenced-icon payloads.

**Hold conclusions (unchanged, verified).** Native L99 hold behavior remains UNVERIFIED; PC-side hold detection via Raw Input remains the feasible path.

---

## 5. Hold-press state machine

### A. PC bridge hold detection

**Deterministic input state machine:**

| State | Entry condition | Exit condition | Action |
|-------|----------------|----------------|--------|
| IDLE | key-up processed, or timeout | key-down | Start timer, go to PRESSED |
| PRESSED | key-down | key-up < 500 ms | Fire short action, go to IDLE |
| PRESSED | key-down | 500–699 ms elapsed, no key-up | Remain in DEAD_ZONE |
| DEAD_ZONE | 500 ms reached | key-up | Suppress short action, go to IDLE |
| DEAD_ZONE | 500–699 ms | 700 ms reached | Fire hold action, go to HELD |
| HELD | 700 ms reached | key-up | Suppress any further action, go to IDLE |
| HOLD_TIMEOUT | key-down, no key-up within timeout | timeout expiry | Reset to IDLE, suppress action |

**Rules:**
- Key-down starts timer.
- Short press below 500 ms fires short action.
- 500–699 ms is a dead zone: no action fires.
- Hold fires once only at 700 ms.
- Key-up resets state to IDLE.
- Short action suppressed after hold.
- Auto-repeat rejected (repeat events ignored while in PRESSED/DEAD_ZONE/HELD).
- Missing key-up recovered via timeout (e.g., 2,000 ms).
- Optional secondary hold at 2,000 ms for a different action.

**Assessment:**

- **WH_KEYBOARD_LL source-identification limitation:** Low-level keyboard hook sees virtual-key codes and scan codes but cannot reliably attribute input to a specific physical device (VID 0C45:800A vs. other keyboards). All keyboard input is global.
- **Raw Input device attribution for 0C45:800A:** Raw Input (`RegisterRawInputDevices`) can attribute keystrokes to a specific HID device by VID/PID, enabling per-device hold detection without global suppression.
- **Device identification vs. global key suppression:** Device identification tells you *which* device sent the key; global suppression (blocking the key from reaching other apps) requires additional hooks and may affect all keyboards. These are separate concerns.
- **Num Lock on/off behavior:** Num Lock toggles VK_NUMPAD/VK_NUMPAD key codes. The bridge must map scan codes or virtual keys independent of Num Lock state, or explicitly handle both states.
- **Process restart while a key is held:** In-flight timer state is lost; key-up may arrive after restart with no matching key-down. The bridge must treat unknown key-up as a no-op and reset on startup.
- **Companion disconnect/reconnect:** Bridge must buffer or drop events during disconnect, resume on reconnect, and not fire stale hold actions after reconnection.

### B. Native L99 hold behavior

**Evidence check from existing touch records and documentation:**

- Touch record structure (image-format.md §3): `type_flags`, `length_flags`, payload = `x1, y1, x2, y2, return_value, unpressed_icon, pressed_icon, goto_page`. No hold-duration or timer field.
- Page 21 touch records: 18 records, 17 type 0xC001 action records with return values 0x0030–0x0040 and goto_page 65535, plus one type 0x8001 Home/back record (return 0x0020, goto_page 1).
- No touch-down/touch-up distinction in record payloads (single record per button, no separate press/release records).
- No hold duration field in touch records.
- No long-press event type identified.
- No timer-based `goto_page` in touch records.
- No repeated return codes indicating auto-repeat or hold.

**Conclusion:** Native L99 hold behavior remains **UNVERIFIED**. No evidence of native hold support exists in touch records or documentation. Do not infer native hold without evidence.

---

## 6. Native hold assessment

Native hold is **UNVERIFIED**. Touch records contain no duration, timer, down/up distinction, or repeat fields. Page 21 touch records use goto_page 65535 for numpad actions and goto_page 1 for Home/back, with no hold semantics. PC-side hold detection via Raw Input is the feasible path; native L99 hold should not be assumed.

---

## 7. Companion POC architecture

**Data flow:**

```
L99 HID event (0C45:800A)
  → Windows bridge (Raw Input device-aware)
    → Deterministic short/hold state machine
      → Companion local API / Satellite interface (HTTP/WebSocket)
        → Companion action or page switch
```

**Design:**

- **17 logical keys:** 16 action keys (no HOME/menu key). Mapped from L99 physical keyboard return values (0x0030-0x0040) and screen Numpad make codes (e.g. 79 -> numpad_1, 80 -> numpad_2).
- Screen Numpad keys are mapped by make_code plus relevant E0/flags, NOT by VKey, so Num Lock ON/OFF produces the same logical key.
- L99 physical keys and screen Numpad share MI_00 and are distinguishable only by key codes (make code + E0/flags), not by Raw Input device handle.
- HOME (0x0020) is screen-internal navigation and emits no Windows input event; it is absent from the Windows logical-key map.
- **Page switching:** Companion actions switch pages via Companion page-switch commands; bridge does not touch L99 firmware.
- **Repeat suppression:** Auto-repeat HID events ignored while key is in PRESSED/DEAD_ZONE/HELD state.
- **Reconnect behavior:** On Companion disconnect, bridge stops sending and buffers recent state; on reconnect, resets state machines (no stale holds) and resumes.
- **Configuration format:** JSON file mapping logical key ID → Companion action (short), Companion action (hold), device VID/PID filter, thresholds (short_ms=500, hold_ms=700, secondary_hold_ms=2000).
- **Structured logs:** JSON lines with timestamp, logical key, event type (down/up/short/hold/suppressed/repeat_ignored), device VID/PID, Companion API result.
- **Provider-agnostic:** HID capture and hold-detection core separated from Companion provider adapter, so a future Macro Deck provider can reuse the core.

**Firmware-free:** No L99 flash, no touch-record changes, no resource modification. Companion receives keyboard events as external input.

---

## 8. Acceptance tests

1. Short press (< 500 ms) on any logical key fires exactly one Companion short action; no hold action.
2. Hold (≥ 700 ms) fires exactly one Companion hold action; no short action.
3. Press held 500–699 ms then released fires no action.
4. Auto-repeat HID events while held are suppressed (no duplicate Companion actions).
5. Missing key-up: state resets after timeout; no stale action fires.
6. Process restart with a key held: no action fires from orphaned key-up.
7. Companion disconnect during hold: no action sent; reconnect resets state.
8. HOME key short vs. hold trigger different Companion actions.
9. Raw Input attributes events to 0C45:800A specifically (not other keyboards).
10. Structured log contains one JSON line per state transition with correct fields.

---

## 9. Safety constraints

- No USB/HID/COM writes from this repository.
- No updater execution.
- No flashing.
- No bootloader.
- No traffic replay.
- No BIN or EXE modification.
- No checksum scanner.
- No new generic scanner.
- No commit, tag, push, release, stage, or version change.
- Read-only analysis only.

---

## 10. Exact next implementation task

"Implement a firmware-free, input-only Windows bridge POC with device-aware HID attribution, deterministic short/hold detection, and a Bitfocus Companion provider."

Do not implement it in this task.

---

## 11. Commands run

```
git status --short
git log --oneline -10
```

---

## 12. Files modified

- Created: `docs\NATIVE_WIDGET_AND_COMPANION_DESIGN.md` (new, untracked)
- No existing files modified.