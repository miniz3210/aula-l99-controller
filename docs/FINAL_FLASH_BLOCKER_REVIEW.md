# Final Flash Blocker Review — AULA L99 Screen Resource Image

**Status:** Offline review only. No hardware access, no updater execution, no flashing.
**Decision:** NO-GO
**Release:** v0.4.0
**Commit:** 53b33da

## Scope

This review resolves the final offline flash blockers for the patched screen resource image
`patched_UartTFT-II_Flash.bin` (SHA-256 `315f68d5...`, size 127,599,044 bytes). Three focus areas:

1. Image-level checksum
2. UI-only versus combined HFD write scope
3. Interrupted-write recovery behavior

No EXE was executed and no hardware was accessed. Classifications follow the project policy:
VERIFIED, STRONG_INFERENCE, UNKNOWN, NOT_REQUIRED.

---

## 1. Image-level Checksum

### Evidence

- Per-packet CRC32 is VERIFIED in both ISP tools (`L99 ISP V1.23.exe`, `HFD_ISP_TOOL_V1.31.exe`)
  via the `4A 30 | offset:LE32 | payload_length:LE16 | payload | CRC32:LE32` frame format and the
  reflected IEEE polynomial (init=0, xorout=0). `123456789` → `0x2DFD2D88` confirmed.
- Strings `"Mcu code, CRC = "`, `"Flash code, FileCRC = "`, `"  FlashCRC = "`, `"  Len = "` are
  present in both ISP tools at file offset ~0xC000–0xCC00.
- `scripts/patch_l99_numpad_icon.py` writes only the two verified descriptor ranges (341/342) and
  preserves all other bytes exactly. It does NOT update any image-level checksum or metadata field.
- `scripts/flash_checksum_scanner.py` performed a structured offline scan over all fixed-structure
  regions (main header, page table, startup animation, first/last 64 KiB, header words) testing
  CRC16/MODBUS, CRC32 reflected IEEE, standard CRC-32, and additive 16/32-bit sums. No stored field
  at any plausible field offset matches any tested algorithm over any region. The scanner now supports
  `--mode quick` (targeted structural checks, under 30 seconds) and `--mode deep` (full investigation,
  cached by factory hash, patched hash, scanner version, scanner source hash, algorithm list, and
  region-map hash). No image-level self-checksum field was located.
- No image-level self-checksum field, trailer, or header checksum within
  `UartTFT-II_Flash.bin` was located in static analysis (PE strings, scripts/`analyze_updater_pe.py`,
  scripts/`inspect_l99_descriptor.py`, docs/`FIRMWARE_PACKAGE_MAP.md`, softce `image-format.md`,
  scripts/`flash_checksum_scanner.py`).

### Classification: UNKNOWN

Per-packet CRC32 is separate from any image-level checksum. Lack of an image-level checksum match
in static analysis is NOT proof that no checksum exists. The patched image may contain an image-level
self-checksum that the updater or screen MCU validates; if such a checksum exists and is not updated
by the patcher, the patched image may be rejected or cause runtime corruption.

### Scanner result (classification input)

| Region | Algorithms tested | Stored-field match at any plausible offset |
|--------|-------------------|---------------------------------------------|
| main_header (88 B) | CRC16/MODBUS, CRC32 ref-IEEE, CRC32 std, addsum16, addsum32 | No |
| page_table (360 B) | same 5 | No |
| startup_animation (26,005,628 B) | same 5 | No |
| first_64kiB (65,536 B) | same 5 | No |
| last_64kiB (65,536 B) | same 5 | No |
| header_words_vs_whole_image | same 5 + file_length | No |

Skipped regions (bounds not fixed in `image-format.md`): widget records, font table, sound table,
animation table (beyond startup animation), background descriptors, descriptor banks, all four
display images, UI projects 2-4.

**Scanner classification: UNKNOWN** (no match found; not proof of absence).

This remains a blocker. The image-level self-checksum requirement is unresolved.

---

## 2. UI-only versus Combined HFD Write Scope

### Evidence

- softce `recovery.md`: "Separate UI packages used `HFD_ISP_TOOL_V1.31.exe` with a resource image
  named `UartTFT-II_Flash.bin`, without HFD_Code or keyboard MCU files. The updater still transfers
  the entire resource image." → UI-only packages are confirmed to exist.
- Both ISP tools contain direct string references to all three files:
  `/UartTFT-II_Flash.bin`, `/HFD_Code_V2.2.bin`, `/HFD_Code_V2.3.bin`, `/Flash.ini`.
- The official Screen Reset EXE (194 MB, Enigma Virtual Box container) extracts
  `UartTFT-II_Flash.bin`, `HFD_Code_V2.2.bin`, and `HFD_Code_V2.3.bin`.
- `Flash.ini` maps flash ID `0xEFAA21` to W25N01GV; `6D 01 selector` query selects HFD V2.2/V2.3
  based on flash ID comparison against `0x00EFAA21`.

### Classification: STRONG_INFERENCE (write scope), NOT_REQUIRED (exact UI-only package construction)

- UI-only write scope is STRONG_INFERENCE: UI-only packages are confirmed per softce, but the actual
  write scope performed by the Screen Reset EXE is not established from static analysis alone. A
  combined UI+HFD write is possible because both ISP tools reference all three files.
- Exact UI-only package construction is NOT verified: no verified procedure exists for constructing
  a UI-only package that the updater will accept. Per the decision rules, "If exact UI-only package
  construction is not verified, remain NO-GO."

Write scope cannot be confirmed as VERIFIED. Combined HFD write remains possible but unconfirmed.

---

## 3. Interrupted-write Recovery Behavior

### Evidence

- Timeout string `"Time over!"` exists in both ISP tools at offset ~0xCAFA.
- `"Update flash is OK!!!!!!"` and `"Update flash is fail....."` status strings exist.
- `"Read fail,please check the path!"` string exists.
- `scripts/patch_l99_numpad_icon.py` and the project safety constraints prohibit automatic retry
  after timeout ("Never retries automatically after timeout").
- softce `recovery.md`: "Supplying only UI data does not guarantee recovery after power loss."
- Screen update instructions (in `reset_unzipped/L99 reset firmware 2026.5.25`): after update
  completes, "switch the keyboard off and on again, then unplug and reinsert the keyboard."
- softce `recovery.md` on Fn+X→0→6: "That attempt did not produce the expected result on our
  specimen. ... Fn+Space for approximately five seconds allowed updating to start. This is an
  observation of one configuration, not a universal replacement for the official procedure across
  revisions."
- No explicit interrupted-write recovery path (resume, re-send, rollback, bad-block handling) was
  found in static analysis of either ISP tool or the Screen Reset EXE.

### Classification: UNKNOWN (recovery behavior), NOT_REQUIRED (manual re-entry vs automatic recovery distinguished)

- Automatic software recovery: UNKNOWN — no explicit path found in static analysis.
- Manual re-entry into ISP mode: STRONG_INFERENCE — official instructions describe power cycling
  (switch off/on, unplug/reinsert) and Fn+X→0→6 or Fn+Space as entry methods, but these are not
  verified as universal across hardware revisions.
- Separate automatic software recovery from manual re-entry: automatic recovery is UNKNOWN; manual
  re-entry is described in official instructions but not verified as universal.

Residual brick risk: if a write is interrupted (timeout, power loss, USB disconnect), there is no
verified recovery path in this repository. Software recovery is limited to restoring files from the
official reset package, which is NOT a raw NAND dump and lacks per-device OOB, ECC, bad-block,
calibration, and unique-board data. Hardware NAND recovery may be required if software rollback
fails. This is an explicit, unrecovered brick risk.

---

## 4. Factory versus Patched Images

| Property | Factory `UartTFT-II_Flash.bin` | Patched `patched_UartTFT-II_Flash.bin` |
|---|---|---|
| Size | 127,599,044 bytes (0x079B01C4) | 127,599,044 bytes (preserved) |
| SHA-256 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` | `315f68d5eda99956eb8bb313c9307fd217c19e4f3575e11628496813a0a4f385` |
| Patch scope | — | Descriptors 341/342 only |
| Image-level checksum updated | N/A | NOT updated by patcher |
| Page 21 touch record `0x003B` | Unchanged | Unchanged |
| Re-parses successfully | Yes | Yes |
| Changed bytes | — | 17,891 bytes across 60 range(s) |
| Changed range span | — | 0x0077C446 .. 0x00780A69 (descriptors 341/342) |
| Any field that should change but did not | — | Image-level checksum field (status UNKNOWN) |

The patcher does not update any image-level checksum or metadata field. All bytes outside descriptors
341/342 are preserved exactly.

---

## 5. Reset-package Updater vs UI-only Package Differences

| Aspect | Official Reset Package | UI-only Package |
|---|---|---|
| Contains `UartTFT-II_Flash.bin` | Yes (extracted by Screen Reset EXE) | Yes (per softce) |
| Contains `HFD_Code_V2.2.bin` / `HFD_Code_V2.3.bin` | Yes | No (per softce) |
| Contains keyboard MCU reset EXE | Yes | No |
| Contains `Flash.ini` | Yes | Unknown |
| Write scope | Combined (UI + HFD possibly) | UI only (per softce) |
| Exact package construction verified | No (EVB container, not reverse-engineered) | No — NOT verified |
| Updater acceptance | STRONG_INFERENCE (Screen Reset EXE) | Unknown |

UI-only package construction is not verified. Per decision rules, this keeps the decision at NO-GO.

---

## 6. Timeout, Restart, Bootloader-entry, and Retry Paths

| Path | Status | Evidence |
|---|---|---|
| Timeout (`"Time over!"`) | STRONG_INFERENCE | String present in both ISP tools |
| Automatic retry after timeout | NOT_REQUIRED / prohibited | Project safety constraint: never auto-retry |
| Restart / re-enter ISP mode | STRONG_INFERENCE | Official instructions: power cycle, Fn+X→0→6, Fn+Space (one config only) |
| Bootloader entry | UNKNOWN | Not verified as universal; no bootloader dump |
| Manual re-entry vs automatic recovery | Distinguished | Manual re-entry described; automatic recovery UNKNOWN |

---

## 7. Classification Summary

| Focus Area | Classification | Basis |
|---|---|---|
| Image-level checksum | UNKNOWN | Per-packet CRC32 verified; image-level self-checksum not located |
| UI-only vs combined HFD write scope | STRONG_INFERENCE | UI-only packages confirmed; combined possible; exact UI-only construction NOT verified |
| Interrupted-write recovery | UNKNOWN | Timeout string present; no explicit recovery path; manual re-entry not universal |
| Automatic software recovery | UNKNOWN | No explicit path found |
| Manual re-entry into ISP mode | STRONG_INFERENCE | Official instructions describe power cycle + key sequence (one config) |

---

## 8. Residual Brick Risk (explicit)

If an interrupted write occurs (timeout, power loss, USB disconnect):

1. There is NO verified automatic software recovery path in this repository.
2. Manual re-entry into ISP mode is described in official instructions but NOT verified as universal
   across hardware revisions.
3. Software rollback is limited to restoring files from the official reset package, which is NOT a
   raw NAND dump and lacks per-device OOB, ECC, bad-block, calibration, and unique-board data.
4. Hardware NAND recovery (outside this repository) may be required if software rollback fails.

This brick risk is unrecovered and explicitly acknowledged.

---

## 9. Decision Rules Evaluation

GO requires:
- [ ] Verified updater acceptance of the patched BIN — VERIFIED for ISP tools, STRONG_INFERENCE for Screen Reset EXE
- [ ] Verified package layout — VERIFIED (filename/path exact)
- [ ] Verified UI-only write or explicitly accepted combined write — NOT verified (UI-only package construction NOT verified)
- [ ] Verified checksum handling — PER-PACKET VERIFIED; IMAGE-LEVEL UNKNOWN
- [ ] Verified method to re-enter updater after a failed write — UNKNOWN

All GO requirements are NOT met. Decision remains NO-GO.

**Decision: NO-GO**

Unresolved critical blockers:
1. Image-level self-checksum requirement — per-packet CRC verified; image-level self-checksum not located (scanner classification UNKNOWN).
2. UI-only vs combined HFD write scope — STRONG_INFERENCE only; exact UI-only package construction NOT verified.
3. Recovery behavior after interrupted write — UNKNOWN; residual brick risk explicit.

Until all critical blockers are VERIFIED, no hardware write is permitted.

---

## 10. Exact Next Task

The image-level self-checksum investigation is complete offline: structured scan over all fixed-structure regions
(main header, page table, startup animation, first/last 64 KiB, header words) testing CRC16/MODBUS,
CRC32 reflected IEEE, standard CRC-32, and additive 16/32-bit sums found no stored-field match at any
plausible field offset. Classification: UNKNOWN (not proof of absence).

Remaining tasks to reach GO:
1. Resolve UI-only vs combined HFD write scope as VERIFIED (including exact UI-only package construction).
2. Determine recovery behavior after interrupted write as VERIFIED or explicitly accept residual brick risk.
3. Re-evaluate GO/NO-GO and document as GO only when all critical blockers are VERIFIED.

Continue offline static analysis only — do not execute any EXE or connect hardware.
