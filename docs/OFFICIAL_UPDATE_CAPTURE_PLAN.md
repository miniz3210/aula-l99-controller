# Official Update Capture Plan — AULA L99 Screen Update (L99 ISP V1.23.exe)

**Status:** Capture preparation only. **No hardware access. No updater execution. No flashing. Decision: NO-GO.**

Release: v0.6.1 | Commit: Correct capture target to L99 ISP V1.23 | Decision: NO-GO for modified firmware

## 1. Purpose

Capture one **unchanged official L99 ISP V1.23.exe screen update** to answer open questions that static analysis cannot verify:

1. Which files the updater opens.
2. Whether HFD_Code_V2.2.bin or V2.3.bin is read.
3. Whether UartTFT-II_Flash.bin is read independently.
4. Exact file-open and read order.
5. Exact USB command and transfer order.
6. Whether UI and HFD payloads are both transmitted.
7. Total bytes transferred per payload.
8. Re-enumeration and ISP-entry behavior.
9. FileCRC and FlashCRC behavior.
10. Final success and restart sequence.

This kit prepares the capture procedure, preflight script, capture automation, offline analyser, and synthetic analyser tests. It does **not** perform the update.

## 2. Approved capture target (sole approved target)

The only approved capture target is the original untouched **L99 ISP V1.23.exe** package, previously used successfully twice on this keyboard.

| Field | Value |
|-------|-------|
| Package root | `firmware\unpacked\` |
| Capture target EXE | `L99 ISP V1.23.exe` |
| EXE size (bytes) | 111,008 |
| EXE SHA-256 | `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0` |

All package files are **local/ignored**, not redistributed, not tracked by Git. Hashes must be verified before capture (`Get-FileHash`).

## 3. Package inventory (every file beside the EXE)

Package root: `firmware\unpacked\` (alongside `L99 ISP V1.23.exe`).

### Core package files (hash-verified by preflight)

| File | Size (bytes) | SHA-256 | Role |
|------|-------------|---------|------|
| `L99 ISP V1.23.exe` | 111,008 | `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0` | Screen ISP updater (capture target) |
| `Flash.ini` | 1,571 | `e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c` | ISP tool config (JEDEC -> chip mapping) |
| `HFD_Code_V2.2.bin` | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` | Screen MCU code V2.2 |
| `HFD_Code_V2.3.bin` | 313,504 | `b277823234fcab7137963896493bcb6896fd985fc972354166fcfc584534e37f` | Screen MCU code V2.3 (earlier build bundled with package) |
| `HFD_ISP_TOOL_V1.31.exe` | 99,328 | `3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282` | Alternate ISP tool bundled in package |

> Note: `HFD_Code_V2.3.bin` bundled in this package is the **earlier build** (313,504 bytes, `b2778232...`), not the standalone official V2.3 (313,652 bytes, `a76806ad...`). Identify files by hash, never by filename alone.

### Runtime DLLs beside the EXE (informational, hash-verified by preflight)

| File | Size (bytes) | SHA-256 |
|------|-------------|---------|
| `Qt5Core.dll` | 8,460,552 | `2af418a34f2076b05ee08dc4bedbe6eb7050bcb6b0658a3db2d5d4302af2db45` |
| `Qt5Gui.dll` | 9,857,512 | `6431689ae70b04224017f0ca8d1ace0102ac03ca5d11aa7cdb1108c6d5ab95a8` |
| `Qt5SerialPort.dll` | 158,752 | `333df93739e8afefecb4e4c56b91d22350869aa24d3ba44c66d310cea0de86` |
| `Qt5Svg.dll` | 589,544 | `60bb2aa9d37684ed43a2c5ad8781c0d9af656e1ce1e867ea3a17752970803d87` |
| `Qt5Widgets.dll` | 9,131,304 | `fa3d2383ebe612f83da59207119ea7aac8306a9f165457f7b9d97b875c584` |
| `libEGL.dll` | 67,128 | `d3628f75921b9145e85442f0c77aba7e568bb6b7bd2479ad9c253654b6a6b677` |
| `libGLESv2.dll` | 7,789,416 | `1d31fe6b741850f00a4b93bb21591008826f72b10063f0cf933610230524456d` |
| `opengl32sw.dll` | 15,995,904 | `25ae7577e066fa80519a8f1c314b15cdd22e4a8d3ecd2a36eeccc79e40714a91d` |
| `D3Dcompiler_47.dll` | 3,466,856 | `efbdbbcd0d954f8fdc53467de5d89ad525e4e4a9cfff8a15d07c6fdb350c407f` |
| `libgcc_s_dw2-1.dll` | 113,678 | `aa8180b63a849e755323bb1abe364b654c0eed9b433738fc491e5b64c410ef76` |
| `libstdc++-6.dll` | 1,542,158 | `c05b714b94bab75ddfb77339aa5f48772be7ac2c3e9d7322e2d1549fc0a39cfd` |
| `libwinpthread-1.dll` | 47,104 | `ae1b4fe65da58196fea59b4dc0be64ae68d6ef04497027fadbddbc2dc38d843d` |

### Subdirectories beside the EXE (informational)

`iconengines\`, `imageformats\`, `platforms\`, `styles\`, `translations\` — Qt plugin directories, not opened by the updater as firmware payloads.

### Required at package root for capture (immutable factory reference, not part of this package dir)

| File | Size (bytes) | SHA-256 | Role |
|------|-------------|---------|------|
| `UartTFT-II_Flash.bin` | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` | Factory UI/resource image read by the updater (`/UartTFT-II_Flash.bin`) |

## 4. Explicitly rejected (never part of this capture)

- **Screen Reset EXE** from `L99-reset.zip` / `L99 reset firmware 2026.5.25.zip` (SHA-256 `8d52849afefeadf3a5d28a5e226f2c7a372a9376e1286f35c286d9b820d1ae84`). The reset ZIP remains offline extraction and recovery-reference material only. Do not capture or execute it.
- **patched_UartTFT-II_Flash.bin** (SHA-256 `315f68d5eda99956eb8bb313c9307fd217c19e4f3575e11628496813a0a4f385`). Never used.
- **Renamed or replaced vendor payloads** — any file whose hash does not match the manifest in Section 3.
- **Missing expected package files** — any manifest file absent from `firmware\unpacked\` causes preflight refusal.
- **New UI-only package construction** — not built, not used, not captured.

## 5. Safety constraints (in force)

- Do not run any updater EXE (including L99 ISP V1.23.exe).
- Do not access hardware (no USB, COM, HID).
- Do not flash or write any firmware.
- Do not change the NO-GO decision.
- Do not perform full-CFG recovery.
- Keep vendor files ignored by Git.
- Never use `patched_UartTFT-II_Flash.bin`.
- Never rename or replace vendor payloads.
- Use only untouched official files with verified hashes.

## 6. Machine and connection prerequisites

- Direct motherboard USB port (no hubs, no docking stations, no passthrough).
- Wired mode only (keyboard VID 0C45 / PID 800A; screen VID EEEF / PID 268A on CDC/serial COM).
- Stable power: UPS or direct AC; no battery-only operation.
- Close AULA software and all custom COM/HID/scripts before starting.
- No COM port sharing with other tools.
- No USB driver replacement (no Zadig, WinUSB, libusbK).
- Procmon, USBPcap/Wireshark, and screen-recording installed and licensed.

## 7. Identifying the USB controller for EEEF:268A before capture

1. Open Device Manager, view by "Connection" or locate "Universal Serial Bus controllers."
2. Find the USB controller/hub to which the screen-side device (VID EEEF, PID 268A) is attached.
3. Confirm it is a direct motherboard USB controller (no hub/dongle in the path).
4. Note the controller instance path for USBPcap/Wireshark interface selection.
5. Confirm the screen enumerates as `USB\VID_EEEF&PID_268A` on a CDC/serial COM port.
6. Record the controller identifier; USBPcap capture targets this controller's USB bus.

## 8. Preflight (run before any capture)

`scripts/prepare_official_capture.ps1 -Preflight` performs a preflight-only check:

- Performs no hardware access.
- Launches no EXE.
- Verifies package hashes against Section 3 manifest.
- Verifies Procmon, Wireshark, and USBPcap availability.
- Verifies adequate free disk space.
- Creates an empty timestamped capture directory.
- Prints `READY` or `NOT READY`.

Any hash mismatch, missing package file, forbidden file, missing tool, or insufficient disk space yields `NOT READY`.

## 9. Capture procedure

### 9.1 Before opening the updater (capture must be running first)

1. Run preflight; must print `READY`. Abort on `NOT READY`.
2. Verify all official file hashes (`Get-FileHash -Algorithm SHA256`). Abort on mismatch.
3. Start Procmon with the filters in Section 10; capture to PML.
4. Start USBPcap/Wireshark on the screen-side USB controller for EEEF:268A; capture to PCAPNG.
5. Start screen recording (lossless, timestamps) of the built-in display and updater window.
6. Confirm all three captures are actively recording.

### 9.2 Run the update (not performed in this task)

7. Open L99 ISP V1.23.exe from the untouched package directory.
8. Start the update.
9. Continue all captures for **30 seconds after** success/restart or abort.
10. Stop captures. Export Procmon to CSV. Save Wireshark PCAPNG. Save screen recording.

### 9.3 Abort conditions before Start

- Any package file hash mismatch.
- Any missing expected package file.
- Any forbidden file present (Screen Reset EXE, patched UI images).
- Monitoring tooling not active.
- Power or USB stability cannot be guaranteed.
- Decision remains NO-GO.

### 9.4 Prohibited after erase/write begins

- Do not disconnect USB.
- Do not power-cycle or reset the device.
- Do not run other USB/COM/HID tools against the device.
- Do not force mode or override safety checks.
- Do not auto-retry after timeout.
- Do not close or kill the updater.
- Do not modify any file in the updater package directory.
- Do not interact with the screen or keyboard.
- Do not interrupt captures.

## 10. Procmon filters

| Filter | Value |
|--------|-------|
| Process | `L99 ISP V1.23.exe` (exact) plus expected child process names |
| Operation | CreateFile |
| Operation | ReadFile |
| Operation | WriteFile |
| Operation | QueryOpen |
| Operation | QueryStandardInformationFile |
| Operation | CloseFile |
| Path | `firmware\unpacked\` package directory and firmware filenames |

Expected child processes are detected and reported by `scripts/analyse_official_capture.py` without launching any EXE (offline static analysis of process/child-process names from capture artefacts). Export to CSV for offline analysis.

## 11. USBPcap / Wireshark capture

- Capture the entire USB controller for the screen-side device (VID EEEF, PID 268A).
- Record before, during, and after the update.
- Capture all Bulk OUT transfers, control transfers, and device disconnect/reconnect (re-enumeration) events.
- Save PCAPNG.

## 12. Screen recording

- Record the built-in screen: pre-update, update progress, post-update/restart.
- Capture About page, Mini Numpad page (page 21), error/recovery screens.
- Lossless video with timestamps.

## 13. Analyser inputs and outputs

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

## 14. Questions the capture will answer

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

## 15. Deliverables

- `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md` — this document.
- `scripts/prepare_official_capture.ps1` — preflight-only environment verification and prerequisites check.
- `scripts/analyse_official_capture.py` — offline analyser for Procmon CSV + PCAPNG.
- `tests/test_analyse_official_capture.py` — synthetic analyser tests (no vendor firmware).

## 16. Scope statement

This capture targets **only** what L99 ISP V1.23.exe actually reads, extracts, and transmits. It does **not** verify the reset-package updater (Screen Reset EXE from L99-reset.zip) and does **not** verify modified UI acceptance (patched_UartTFT-II_Flash.bin).

## 17. Decision remains NO-GO

This capture kit prepares observation only. No hardware write is permitted until all critical blockers (image-level self-checksum, write scope, interrupted-write recovery) are VERIFIED.
