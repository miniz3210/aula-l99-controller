# Recovery and Package Compatibility Matrix — AULA L99

**Scope:** Offline review only. No hardware access, no updater execution.
**Default decision:** NO-GO unless all required compatibility checks are verified.

## 1. Component Inventory

| Component | File | Size (bytes) | SHA-256 | Status |
|-----------|------|-------------|---------|--------|
| Official Reset ZIP | `L99-reset.zip` (2026-05-25) | 45,080,624 | `e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3` | Local/ignored |
| Screen Reset EXE | within ZIP | 194,946,048 | `8d52849afefeadf3a5d28a5e226f2c7a372a9376e1286f35c286d9b820d1ae84` | Local/ignored |
| Keyboard Reset EXE | within ZIP | ~2,200,000 | unknown | Local/ignored |
| Screen Resource Image | `UartTFT-II_Flash.bin` | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` | Factory reference |
| Patched Resource Image | `patched_UartTFT-II_Flash.bin` | 127,599,044 | `315f68d5eda99956eb8bb313c9307fd217c19e4f3575e11628496813a0a4f385` | Working copy |
| Screen MCU Code V2.2 | `HFD_Code_V2.2.bin` | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` | Factory reference |
| Screen MCU Code V2.3 (official) | `HFD_Code_V2.3.bin` | 313,652 | `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03` | Factory reference |
| Screen MCU Code V2.3 (earlier) | `HFD_Code_V2.3.bin` | 313,504 | `b277823234fcab7137963896493bcb6896fd985fc972354166fcfc584534e37f` | Duplicate name, different hash |
| Screen ISP Tool V1.23 | `L99 ISP V1.23.exe` | 111,008 | `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0` | Local/ignored (EVB-unpacked inner PE) |
| Screen ISP Tool V1.31 | `HFD_ISP_TOOL_V1.31.exe` | 99,328 | `3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282` | Local/ignored (EVB-unpacked inner PE) |
| ISP Tool Config | `Flash.ini` | 1,571 | unknown | Local/ignored |

## 2. Updater/Package Relationship Matrix

| Question | L99 ISP V1.23.exe | HFD_ISP_TOOL_V1.31.exe | Official 2026-05-25 Screen Reset EXE |
|----------|-------------------|------------------------|--------------------------------------|
| Accepts `UartTFT-II_Flash.bin` directly? | **VERIFIED** (direct string ref `/UartTFT-II_Flash.bin`) | **VERIFIED** (direct string ref `/UartTFT-II_Flash.bin`) | STRONG_INFERENCE (extracts it; EVB container) |
| Writes UI resources only? | STRONG_INFERENCE (softce: UI-only packages confirmed) | STRONG_INFERENCE (softce: UI-only packages confirmed) | Unknown |
| Also rewrites `HFD_Code`? | Unknown | Unknown | Unknown |
| Selects HFD V2.2 vs V2.3? | STRONG_INFERENCE (flash ID `0xEFAA21` selector) | STRONG_INFERENCE (flash ID `0xEFAA21` selector) | Unknown (mechanism not established) |
| Performs size check? | STRONG_INFERENCE (error strings present) | STRONG_INFERENCE (error strings present) | Unknown |
| Performs CRC/hash check? | **VERIFIED** (CRC32 reflected IEEE; FileCRC/FlashCRC strings) | **VERIFIED** (CRC32 reflected IEEE; FileCRC/FlashCRC strings) | Unknown |
| Performs filename check? | **VERIFIED** (exact `/UartTFT-II_Flash.bin` ref) | **VERIFIED** (exact `/UartTFT-II_Flash.bin` ref) | Unknown |
| Performs path check? | **VERIFIED** (root-relative alongside `Flash.ini`) | **VERIFIED** (root-relative alongside `Flash.ini`) | Unknown |
| Performs flash-ID check? | STRONG_INFERENCE (`0xEFAA21` string) | STRONG_INFERENCE (`0xEFAA21` string) | Unknown |
| Performs hardware-ID check? | STRONG_INFERENCE ("Fail to Connect a 268x device"; `268A`) | STRONG_INFERENCE ("Fail to Connect a 268x device"; `268A`) | Unknown |
| Performs version check? | STRONG_INFERENCE (HFD V2.2/V2.3 via flash ID) | STRONG_INFERENCE (HFD V2.2/V2.3 via flash ID) | Unknown |
| Post-write read-back verification? | STRONG_INFERENCE ("Update flash is OK/fail"; "Read fail") | STRONG_INFERENCE ("Update flash is OK/fail"; "Read fail") | Unknown |
| Transmits full 127,599,044-byte image? | **VERIFIED** (softce: entire resource image transferred) | **VERIFIED** (softce: entire resource image transferred) | Unknown |
| Transmits selected ranges only? | Unknown | Unknown | Unknown |
| Local/ignored binary? | Yes | Yes | Yes (within ZIP) |
| Executed in this task? | No | No | No |

## 3. Compatibility Check Status

| Check ID | Check | Status | Blocker? |
|----------|-------|--------|----------|
| C1 | Factory `UartTFT-II_Flash.bin` SHA-256 matches `4cb3fa5c...` | Verified | No |
| C2 | Patched image SHA-256 matches `315f68d5...` | Verified | No |
| C3 | Patch limited to descriptors 341/342 at verified ranges | Verified | No |
| C4 | Page 21 touch record `0x003B` unchanged | Verified | No |
| C5 | Patched image re-parses successfully | Verified | No |
| C6 | Updater accepts `UartTFT-II_Flash.bin` directly | **VERIFIED** (ISP tools) / STRONG_INFERENCE (Screen Reset EXE) | Yes (Screen Reset EXE path unresolved) |
| C7 | Updater writes UI resources only vs also `HFD_Code` | STRONG_INFERENCE | Yes |
| C8 | HFD V2.2 vs V2.3 selection mechanism | STRONG_INFERENCE (flash ID `0xEFAA21`) | Yes |
| C9 | Size check (127,599,044 bytes) | **VERIFIED** (size confirmed; enforcement inferred) | No |
| C10 | CRC/hash check on image | **VERIFIED** (CRC32 reflected IEEE per-packet; FileCRC/FlashCRC strings) | No |
| C11 | Filename check (`UartTFT-II_Flash.bin`) | **VERIFIED** (exact string ref) | No |
| C12 | Path check (updater folder placement) | **VERIFIED** (root-relative alongside `Flash.ini`) | No |
| C13 | Flash-ID check | STRONG_INFERENCE (`0xEFAA21`; Flash.ini JEDEC→chip mapping) | Yes |
| C14 | Hardware-ID check (VID EEEF / PID 268A) | STRONG_INFERENCE ("Fail to Connect a 268x device"; Qt5SerialPort VID/PID) | Yes |
| C15 | Version check (HFD V2.2/V2.3, screen MCU, UI/project) | STRONG_INFERENCE (flash-ID-based HFD selection; V1.31 unresolved) | Yes |
| C16 | Internal checksum/metadata update required for patched image? | UNKNOWN (per-packet CRC verified; image-level self-checksum not located) | Yes |
| C17 | Full-image vs selected-range transmission | **VERIFIED** (full image transferred per softce) | No |
| C18 | Post-write read-back verification available? | STRONG_INFERENCE (status strings exist; arbitrary read-back not established) | Yes |
| C19 | Recovery behavior after interrupted write | UNKNOWN | Yes |
| C20 | Official reset package is not a raw NAND dump | Verified | No (limits recovery scope) |
| C21 | About-page V1.31 must not be assumed to identify screen firmware | Verified | No |

## 4. UI-Only vs Full-Reset Conclusion

**STRONG_INFERENCE.** softce recovery.md confirms separate UI packages used `HFD_ISP_TOOL_V1.31.exe` with `UartTFT-II_Flash.bin` without HFD_Code or keyboard MCU files. However, both ISP tools statically reference all three files (`/UartTFT-II_Flash.bin`, `/HFD_Code_V2.2.bin`, `/HFD_Code_V2.3.bin`), so a combined UI+HFD write is possible. The actual write scope performed by the Screen Reset EXE is not established from static analysis alone.

Exact UI-only package construction is **NOT verified**. Per project decision rules, if exact UI-only package construction is not verified, remain NO-GO.

This remains a blocker: if `HFD_Code` is also rewritten, the patched resource image may be paired with incompatible screen MCU code.

## 5. Checksum/CRC Conclusion

**VERIFIED / UNKNOWN.** Per-packet CRC32 (reflected IEEE polynomial, init=0, xorout=0) is verified in the ISP tools via the `4A 30 | offset:LE32 | payload_length:LE16 | payload | CRC32:LE32` frame format and FileCRC/FlashCRC strings. Per-packet CRC32 is separate from any image-level checksum.

Whether `UartTFT-II_Flash.bin` contains an additional image-level self-checksum beyond per-packet CRC that the updater or screen MCU validates is **not located in static analysis**. `scripts/flash_checksum_scanner.py` scans fixed-structure regions only, supports `--mode quick` (under 30 seconds) and `--mode deep` (cached by factory hash, patched hash, scanner version, scanner source hash, algorithm list, and region-map hash). Lack of an image-level checksum match is not proof that no checksum exists. The patcher writes only the two verified descriptor ranges and does not update any image-level checksum or metadata field. This remains a blocker.

## 6. Interrupted-write Recovery Conclusion

**UNKNOWN.** Timeout string `"Time over!"` exists in both ISP tools, and status strings `"Update flash is OK!!!!!!"` / `"Update flash is fail....."` exist, but no explicit interrupted-write recovery path (resume, re-send, rollback) was found in static analysis of either ISP tool or the Screen Reset EXE.

Automatic software recovery: **UNKNOWN** — no explicit path found.
Manual re-entry into ISP mode: **STRONG_INFERENCE** — official instructions describe power cycling (switch off/on, unplug/reinsert) and Fn+X→0→6 or Fn+Space entry, but these are observations of one configuration, not verified as universal across hardware revisions.

Residual brick risk: if an interrupted write occurs (timeout, power loss, USB disconnect), there is NO verified recovery path in this repository. Software recovery is limited to restoring files from the official reset package, which is NOT a raw NAND dump and lacks per-device OOB, ECC, bad-block, calibration, and unique-board data. Hardware NAND recovery may be required if software rollback fails. This brick risk is explicit and unrecovered.

## 7. About-Page Version Note

The device About page displays `V1.31`. The source of this version is unresolved. It may be keyboard MCU,
screen MCU, UI/project version, or whole-device product version. It must **not** be assumed to identify the
screen resource image, HFD image, or PC updater. `HFD_ISP_TOOL_V1.31.exe` version must not be equated
automatically with the About-page version.

## 7. NAND Recovery Note

The official reset package is **not** a raw NAND dump. It lacks verified per-device OOB, ECC, bad-block,
calibration, and unique-board data. Software recovery is limited to restoring files included in the package.
Hardware NAND recovery is required if software rollback fails.

## 8. GO / NO-GO Decision

**Decision: NO-GO**

Per project policy, NO-GO changes to GO only when all critical blockers are VERIFIED:

- updater acceptance: **VERIFIED** (ISP tools) / STRONG_INFERENCE (Screen Reset EXE)
- required package layout: **VERIFIED** (filename/path exact)
- write scope: **STRONG_INFERENCE** (full image; UI-only vs combined HFD not fully resolved; exact UI-only package construction NOT verified)
- checksum/CRC handling: **VERIFIED** (per-packet CRC) / UNKNOWN (image-level self-checksum)
- hardware compatibility checks: **STRONG_INFERENCE** (flash-ID/268x device checks)
- recovery path: **UNKNOWN** (no explicit interrupted-write recovery found; residual brick risk explicit)

Unresolved critical blockers:
1. Image-level self-checksum requirement — per-packet CRC verified, image-level self-checksum not located.
2. UI-only vs combined HFD_Code write scope — STRONG_INFERENCE only; exact UI-only package construction NOT verified.
3. Recovery behavior after interrupted write — UNKNOWN; residual brick risk explicit.

No hardware write is permitted until all critical blockers are VERIFIED.

## 9. Conditions to Change to GO

1. Image-level self-checksum requirement determined and satisfied or confirmed unnecessary.
2. Write scope confirmed (UI-only vs combined HFD_Code rewrite) as VERIFIED — including exact UI-only package construction.
3. Recovery behavior after interrupted write determined as VERIFIED or explicitly accepted as risk (residual brick risk acknowledged).
4. All remaining STRONG_INFERENCE items either VERIFIED or explicitly accepted as risk.
5. Rollback and recovery limits explicitly accepted.
6. GO / NO-GO re-evaluated and documented as GO.

## 10. Exact Next Task

Resolve remaining critical blockers offline: (1) determine whether `UartTFT-II_Flash.bin` contains an image-level self-checksum beyond per-packet CRC; (2) confirm write scope (UI-only vs combined HFD_Code rewrite) as VERIFIED — including exact UI-only package construction; (3) determine recovery behavior after interrupted write as VERIFIED or explicitly accept residual brick risk. Continue offline static analysis only — do not execute any EXE or connect hardware.