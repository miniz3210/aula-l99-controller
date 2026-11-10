# Official Update Capture Plan — AULA L99 Screen Update

**Status:** Capture preparation only. **No hardware access. No updater execution. No flashing. Decision: NO-GO.**

Release: v0.5.0 | Commit: c82dc35 | Decision: NO-GO for modified firmware

## 1. Purpose

Capture one **unchanged official AULA L99 screen update** to answer ten open questions that static analysis cannot verify:

1. Which files the updater opens.
2. Whether HFD_Code_V2.2.bin or V2.3.bin is read.
3. Whether UartTFT-II_Flash.bin is read independently.
4. Exact file-open and read order.
5. Exact USB command and transfer order.
6. Whether UI and HFD payloads are both transmitted.
7. Total bytes transferred for each payload.
8. Re-enumeration and ISP-entry behavior.
9. FileCRC and FlashCRC behavior.
10. Final success and restart sequence.

This kit prepares the capture procedure, capture automation script, offline analyser, and synthetic analyser tests. It does **not** perform the update.

## 2. Safety constraints (in force)

- Do not run any updater EXE.
- Do not access hardware.
- Do not flash or write any firmware.
- Do not change the NO-GO decision.
- Do not perform full-CFG recovery.
- Keep vendor files ignored by Git.
- Never use `patched_UartTFT-II_Flash.bin`.
- Never rename or replace vendor payloads.
- Use only untouched official files with verified hashes.

## 3. Required files (verified hashes, untouched, local/ignored)

| File | Size (bytes) | SHA-256 | Role |
|------|-------------|---------|------|
| `UartTFT-II_Flash.bin` | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` | Factory UI/resource image |
| `HFD_Code_V2.2.bin` | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` | Screen MCU code V2.2 |
| `HFD_Code_V2.3.bin` (official) | 313,652 | `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03` | Screen MCU code V2.3 |
| `Flash.ini` | 1,571 | `e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c` | ISP config |
| Official Reset ZIP (2026-05-25) | 45,080,624 | `e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3` | Recovery rollback only |

All files are **local/ignored**, not redistributed, not tracked by Git. Hashes must be verified before the capture (`Get-FileHash`).

## 4. Machine and connection prerequisites

- Direct motherboard USB port (no hubs, no docking stations, no passthrough).
- Wired mode only (keyboard VID 0C45 / PID 800A; screen VID EEEF / PID 268A on CDC/serial COM).
- Stable power: UPS or direct AC; no battery-only operation.
- Close AULA software and all custom COM/HID/scripts before starting.
- No COM port sharing with other tools.
- No USB driver replacement (no Zadig, WinUSB, libusbK).
- Procmon, USBPcap/Wireshark, and screen-recording installed and licensed.

## 5. Capture procedure

### 5.1 Before opening the updater (capture must be running first)

1. Verify all official file hashes (`Get-FileHash -Algorithm SHA256`). Abort on mismatch.
2. Start Procmon with the filters in Section 6; capture to PML.
3. Start USBPcap/Wireshark on the screen-side USB bus; capture to PCAPNG.
4. Start screen recording (lossless, timestamps) of the built-in display and updater window.
5. Confirm all three captures are actively recording.

### 5.2 Run the update (not performed in this task)

6. Open the official updater from an untouched package directory.
7. Start the update.
8. Continue all captures for **30 seconds after** success/restart or abort.
9. Stop captures. Export Procmon to CSV. Save Wireshark PCAPNG. Save screen recording.

### 5.3 Abort conditions before Start

- Any official file hash mismatch.
- Any byte outside expected ranges changed in any vendor payload.
- Monitoring tooling not active.
- Power or USB stability cannot be guaranteed.
- Decision remains NO-GO.

### 5.4 Prohibited after erase/write begins

- Do not disconnect USB.
- Do not power-cycle or reset the device.
- Do not run other USB/COM/HID tools against the device.
- Do not force mode or override safety checks.
- Do not auto-retry after timeout.
- Do not close or kill the updater.
- Do not modify any file in the updater package directory.
- Do not interact with the screen or keyboard.
- Do not interrupt captures.

## 6. Procmon filters

| Filter | Value |
|--------|-------|
| Process | Updater process name (exact) |
| Operation | CreateFile |
| Operation | ReadFile |
| Operation | WriteFile |
| Operation | QueryOpen |
| Operation | QueryStandardInformationFile |
| Operation | CloseFile |
| Path | Updater package directory and firmware filenames |

Export to CSV for offline analysis.

## 7. USBPcap / Wireshark capture

- Capture the entire USB controller for the screen-side device (VID EEEF, PID 268A).
- Record before, during, and after the update.
- Capture all Bulk OUT transfers, control transfers, and device disconnect/reconnect (re-enumeration) events.
- Save PCAPNG.

## 8. Screen recording

- Record the built-in screen: pre-update, update progress, post-update/restart.
- Capture About page, Mini Numpad page (page 21), error/recovery screens.
- Lossless video with timestamps.

## 9. Analyser inputs and outputs

Inputs (offline, never hardware):

- Exported Procmon CSV.
- USBPcap/Wireshark PCAPNG.
- Expected file hash manifest.

Outputs:

- Inventory of opened firmware files and read order.
- Bytes read per file.
- HFD V2.2 / V2.3 / UI access identification.
- USB transfer sizes, sequence, and timing.
- UI vs HFD payload transmission (both, one, or neither).
- Total bytes transferred per payload.
- Re-enumeration and ISP-entry events.
- FileCRC and FlashCRC behavior.
- Final success and restart sequence.
- Evidence-vs-inference classification for every finding.

Constraints:

- Remains offline.
- Never opens COM/USB.
- Never executes an updater.
- Distinguishes evidence from inference.

## 10. Questions the capture will answer

| # | Question |
|---|----------|
| 1 | Which files does the updater open? |
| 2 | Is HFD_Code_V2.2.bin or V2.3.bin read? |
| 3 | Is UartTFT-II_Flash.bin read independently? |
| 4 | Exact file-open and read order? |
| 5 | Exact USB command and transfer order? |
| 6 | Are UI and HFD payloads both transmitted? |
| 7 | Total bytes transferred per payload? |
| 8 | Re-enumeration and ISP-entry behavior? |
| 9 | FileCRC and FlashCRC behavior? |
| 10 | Final success and restart sequence? |

## 11. Deliverables

- `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md` — this document.
- `scripts/prepare_official_capture.ps1` — capture environment verification and prerequisites check.
- `scripts/analyse_official_capture.py` — offline analyser for Procmon CSV + PCAPNG.
- `tests/test_analyse_official_capture.py` — synthetic analyser tests (no vendor firmware).

## 12. Decision remains NO-GO

This capture kit prepares observation only. No hardware write is permitted until all critical blockers (image-level self-checksum, write scope, interrupted-write recovery) are VERIFIED.