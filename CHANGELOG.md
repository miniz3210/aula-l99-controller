# Changelog

All notable research milestones, software integration checkpoints, and safety gates for the AULA L99 controller project are documented in this file.

## [Unreleased]

### 2026-11-24 — V2.2 Hardware Baseline Lock & Host-Path Dynamic Icon Patch (`DI-PATCH-A-FINAL`)

#### 1. Official Update Capture & V2.2 Hardware Lock (`VERIFIED_EXACT_MATCH`)
- **Physical Hardware & Firmware Identity:** Passive USB (`USBPcap1`) and Procmon capture of untouched `L99_ISP_中文完整UI_V1.23_156.exe` (`HFD_ISP_TOOL_V1.31.exe`) confirmed Winbond `W25N01GV` SPI NAND (`JEDEC 0xEFAA21` via `6D 01` query / `7D` response on `OUT EP3` / `IN EP2`) and exact byte-for-byte match (`0` diffs across 150 `0x4A 0x30` frames = `305,800` bytes) with `firmware/unpacked/HFD_Code_V2.2.bin` (SHA-256 `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf`, base `0x6000A000`).
- **CRC-32 & Framing Rules:** Verified raw CRC-32 (`poly=0x04C11DB7` reflected, `init=0`, `xorout=0`) = `0xCFFD42D9` for `HFD_Code_V2.2.bin` (150 `0x4A 0x30` frames: 8-byte header + 2048-byte data + 4-byte trailer; last frame 648 data bytes) and `0xA696D067` for official UI `screen_v1.23` (`95,473,788` bytes, SHA-256 `903a4f...`). Command packets `0x4C`/`0x4E`/`0x6E`/`0x4F` end with raw CRC-32; `0x4B` reply is not CRC.
- **Memory Boundaries & Target Scope:** Bootloader `0x60000000–0x60009FFF` locked as strictly off-limits; application base locked at `0x6000A000`. The official updater in this capture transferred `V2.2`; `HFD_Code_V2.3` is not the current target.
- **Unverified Items (Preserved):** Physical NAND offset `0` storage, UI partition at NAND `0x00080000`, unused space after `0x4AA88`, and `V2.3` hardware compatibility remain unverified until `FW-SAFE-A`.

#### 2. Native Runtime Tracing & Host Protocol Mapping (`DI-TRACE-*`, `DI-ICON-A`, `DI-HOST-A`)
- **Native Instrumentation (`DI-TRACE-NATIVE` / `DI-TRACE-CORRELATE`):** `PASS_NATIVE_EVENT_CAPTURE` & `PASS_NATIVE_CORRELATION`. Process-isolated CEmu execution on `HFD_Code_V2.2.bin` captured `128,173` sampled instruction events (`30` UART RX, `356` LCD command, `2,100` sampled LCD pixel writes, `20` UART TX, `81,798` NAND events) and rebuilt V2.2 function boundaries independently (no V2.3 boundaries reused).
- **End-to-End Display Chain (`DI-TRACE-EA` v1.3.0 / `DI-ICON-A`):** `PASS_EA_CAPTURE`, `PASS_RUNTIME_CHAIN`, and `PASS_DYNAMIC_ICON_EMULATOR_INJECTED`.
  - UART ISR `FUN_600420ec` $\to$ RX buffer `0x0081d064..0x0081d06d` $\to$ parser `FUN_600421e4` / dispatcher `FUN_60040594`. Page ID stored at `0x008201ea`.
  - Display pipeline: NAND QSPI $\to$ DMA ch3 $\to$ staging `0x00874xxx` $\to$ CPU $\to$ front framebuffer `0x00875000` (100% match with `lcd_buf`) $\to$ DMA ch15 (`640 B/line`, SADDR ends at `0x0090b000`) $\to$ LCD `0x20000002`.
  - Same-page `64x64` Icon A$\to$B$\to$C (`C` = random noise) updated exact inside rect with `0` pixels changed outside; firmware does not idle-refresh, so patch pushes the rect.
- **Stock VP Mapping (`DI-HOST-A`):** `PASS_HOST_PROBE_CAPTURE` (`FB_NOT_REACHABLE_BY_LINEAR_VP`). Linear `VP n` maps to RAM `0x0080e4a4 + 2n` (usable `0x0000–0x1FFF`; `VP >= 0x3000` rejected). **Hazard:** `VP 0x2000` aliases system `VP 0x7000` (page variable) — never write `VP 0x2000–0x6FFF` from the adapter. Commands with real effect: `0x03`, `0x10`, `0x61` (`258`-byte frames accepted; one `0x10` frame writes `125` words). `fb0` (`0x00875000`) is the composed screen (`fb1` unchanged during page switch). Stock VP widget updates reach LCD without updating `fb0`; OpenDeck icon slots must not overlap VP widgets.

#### 3. Host-Path Dynamic Icon Emulator Patch (`DI-PATCH-A` v1.3.0 $\to$ v1.4.0 `DI-PATCH-A-FINAL`)
- **Transport & Mailbox Layout:** Uses stock `0x10` VP writes only. Pixel buffer at `VP 0x0400` (RAM `0x0080eca4`, max `6,144` px) and mailbox at `VP 0x1F00` (RAM `0x008122a4`: clear `0x0000` $\to$ `x,y,w,h` at `0x1F01–0x1F04` $\to$ GO `0xA55A` $\to$ DONE `0x600D` / ERROR `0xEEEE`).
- **Official UI VP Scan (Page 1 + Page 21):** Bound blocks `0x0000` (p1+p21), `0x0300` (p21 only); free `0x0100–0x02FF`, `0x0400–0x1FFF`.
- **Patch Footprint:** `356` bytes total — `jsri` literal `0x6003ca88` (`ccfd0160 -> a0420560`) at site `0x6003c8ce` in `0x6003c770`, jumping to a `352`-byte trampoline at `0x600542a0` (code cave `0x6005428d–0x600545f7`; free RAM `0x00848000–0x0086bfff` also mapped), exiting via `jmpi` to `0x6001fdcc`.
- **Verification (`DI-PATCH-A` v1.4.0):** `PASS_DYNAMIC_ICON_HOST_PATH_EMULATOR` (`14/14` criteria) on both CEmu NAND and official UI (`screen_v1.23`, patched image `df3a998b...`, `EMULATOR_ONLY_NOT_FOR_FLASH`). Same-page `64x64` icon A$\to$B$\to$C exact, `0` pixels outside rect, persists after 100M steps, page stays 1, regression equal to stock, no self-modify, no NAND writes, originals unchanged.

#### 4. Safety & Next Tasks
- **Safety Gate:** Physical firmware flashing remains **NO-GO**.
- **Open / Next:** `FW-SAFE-A` (checksum/bootloader/recovery gates), `UI-REBASE-A` (remaining UI pages VP scan), real-time upload latency, and live OpenDeck integration (`OD2-A-R1`, `HW2`).

---

### 2026-11-23 — OpenDeck Live Windows Software Integration (`OD1-R2`, `OD1-R3-H1`, `OD2-B-R2`)
- **Live Virtual Device (`OD1-R2`):** `PASS_VERIFIED_LIVE_WINDOWS` — AULA L99 4x4 virtual device registered in OpenDeck; Rust Named Pipe IPC verified; touch `0x50` triggered live OpenDeck action (Google Open URL executed).
- **Icon Callbacks (`OD1-R3-H1`):** `PASS_VERIFIED_LIVE_WINDOWS` — Genuine `setImage` JPEG callbacks decoded and normalized to PNG (callback count `3 -> 8`, SHA-256 updated, Rust release build passed).
- **Screen Backend Pipeline (`OD2-B-R2`):** `PASS_VERIFIED_LIVE_WINDOWS_TO_MOCK` — Python `CallbackSpoolConsumer` processed `30 CLEAR_POSITION` + `2 SET_IMAGE` events, converted PNG to little-endian RGB565 (`19,200` bytes per `80x120` icon, SHA-256 `4054fd8bf8d20d967ac923cd940056a4e90e2b096ea93e54cbea6d4acafedef4`), and verified duplicate suppression on `MockTransport`.
- **Pending:** `OD2-A-R1` Real Named Pipe Input Adapter integration; `HW2` physical touchscreen transport testing; physical L99 icon/framebuffer delivery unverified; original physical Numpad and Home Navigation must be preserved.

---

### 2026-11-22 — Visible Resource & Touch Integration (`A2-R7-H5`) & Product Direction (`U7.1–U7.5`, `S1–S5`)
- **Offline Visible Resource + Touch (`A2-R7-H5`):** `PASS_VISIBLE_RESOURCE_AND_TOUCH` (VERIFIED OFFLINE) on Page 21 Mini Numpad (Bank 0 ID 21, offset `6624228`, `338` bytes, `13x13` format 2, candidate SHA-256 `66c276756646a642e28e082ae53cfcb5d67689295388c5cb27060a9eb3d291e0`), modifying 5 pixels at `(256,14)-(261,15)` and touch record offset `150602` at `(198,440)` from `0x40 -> 0x41` while staying on Page 21.
- **UI Header & Calculator (`U7.1–U7.5`):** Reproduced image-level header CRC rule offline (length at `0x174`, CRC at `0x178`, complement at `0x17C`, bytes `0x174–0x17F` blanked with `0xFF`). Verified Page 22 Calculator offline (`18` type `0xC001` button records; rendered `1`, `12`, `12+`, `12+3`, `15`; generic `41 FF FF 43 4C` UART frames).
- **Structural Inventory (`S1–S5`):** Confirmed 30-page packed layout (`385` widgets, `187` touch records) without insertion gaps. Page 21 = Mini Numpad; Page 22 = Calculator; Page 19 = dynamic-widget candidate; Page 20 = Play. Rejected S5 report due to mislabeled page IDs and invalid JSON hex literals.

---

### 2026-11-21 — AutoResearch Workflow & UI/NAND U1–U6 Validation
- **AutoResearch v1–v5:** Established unattended Ubuntu REA (`10.1.0.107`) workflow using Ghidra 12.1.4, Python, and MCore emulator with strict read-only and no-flash safety boundaries.
- **Firmware RAM Relocated Helper:** Identified `1,396`-byte flash-programming routine relocated to RAM `0x00800000` (entry `0x00800004`, byte-identical across V2.2/V2.3, commands `0x06`/`0x05`/`0x02`, 24-bit addressing, 256-byte page splitting).
- **U1–U6 Touch Validation:** Corrected 12-byte page record, 5-byte widget header, and 3-byte touch header structures; achieved `30/30` round-trips across `385` widget and `187` touch records; verified all `17` Page 21 touch buttons (`0x30–0x40`, UART `41 FF FF 00 XX`) plus Home navigation (`0x8001` $\to$ Page 1) offline (`VERIFIED OFFLINE`).

---

### 2026-11-20 — Teardown Hardware Identification, Official Manuals & Update Captures (`E52–E54`, `cap4`, `cap5`)
- **Teardown Chip Markings:** Screen sub-board `SI-2686-TFT-3.98 V01` carries MCU **`HFD168BDP`** (QFN68), Winbond **`25N01GV`** SPI NAND, Goodix **`GT911`** touch IC, `SW2` push switch, and test pads `GND/SCK/DIO/RST` (likely PGMCK pin 64 / PGMIO pin 57 / reset, continuity unverified). Keyboard main board carries **`HFD80CP100`** (LQFP100).
- **Bootloader Entry (`cap4` / `cap5`):** `Fn + X + 0 + 6` triggers screen re-enumeration (`0.333s` later) into bootloader `EEEF:268A` (`TEST_1.0`, `COM4`, device ID `0x1971168B`, type `0xEEBA0081`) via non-USB hardware signaling; latched until USB power cycle.
- **Protocol & Manual Findings (`E52–E53`, UI_Editor-II / LT168 / LT268x manuals):**
  - Confirmed `5A A5` Modbus-style serial framing (`0x03` read, `0x10` write, `0x41` touch feedback, `0x61–0x67` extended flash ops) and register map (`0x7000` page, `0x7001` brightness, `0x700B` volume, `0x700D` key-code trigger, `0x7011` serial upgrade, `0x7040` orientation, `0x7042` UI project upgrade).
  - **Hazard:** Never write register `0x7011` (`0x2011`) = `0xAA55` or send extended frames `0x61–0x67` to a live unit.
  - Reconstructed keyboard reset `SN32F290.hex` (`92,148` bytes, SHA-256 `a805de868dfe27de39ff003dbf9c56347fa4e0441d0150a8a6802280c9872799`, Cortex-M0 class, wireless module UART at `0x40054000`, `160x80` ST7735 status LCD) in `E54`.
  - Audited `L99 keyboard Screen reset firmware.exe` (compile timestamp `2026-04-07`, 4 embedded UI images with `10,704,364`-byte header length) and verified `custom_c` minimal image (`0x5B0D07C` bytes, SHA-256 `3B27223F...`) in CEmu (`EMULATOR_ONLY`, not flash-safe).

---

### 2026-11-19 — Deep Firmware Disassembly & Library/Boot Analysis (`E30a–E51`)
- **Compiler & Memory Map (`E30a`, `E32`, `E38`):** Proved little-endian MCore `c0_div` multilib build (`91` byte-identical vendor library functions). V2.3 RAM map: `.data` `0x800800–0x8011F0` (`2,544` bytes), `.bss` `0x801200–0x870E6C` (`457,836` bytes), stack top `0x874FFC`.
- **Flag Routine & Flash Guard (`E43`, `E44`, `E51`):** Flag routine (`C1 0x60036E30` / `C3 0x6002F01C`) erases `0x6000F000` (`4 KiB`) and jumps through `0x60000000`. Internal flash helper (`C1 0x60047E8C` / `C3 0x6003FC74`) checks `[0x60000000, 0x60200000)` with **no lower bound protecting the bootloader**.
- **Framebuffer, Config Block & Peripherals (`E47–E51`):** Confirmed RGB565 page canvas at `0x00875000` (`307,200` bytes ending at `0x8C0000`) pushed via DMA to `0x20000002` (ST7796S-class bus, `168 MHz` clock, PWM1 audio/backlight, GT911 touch I2C `0x28`), config block at UI offset `0x80`, and PC updater `K/L/J/N` frame sequence (`0x800`-byte chunks, raw CRC-32 init `0` no xor).

---

### 2026-11-18 — Targeted SerialPortTool & Safe Flash Blockers Audit
- Completed V4 full-firmware pipeline (`19,460/19,463` functions decompiled) and `SerialPortTool` targeted analysis (`34` jobs, `0` failures).
- Verified `P21_FINAL_ACCEPTANCE.md` (`19`-byte record layout, `numpad_1` at header `0x00024CA9` / payload `0x00024CAC`).
- Audited `DeviceDriver.exe` telemetry (`HM3` / `HM4B`, `C:\Program Files (x86)\AULA L99\data.ini`) and issued `SAFE_FLASH_NOT_READY` gate.

---

### 2026-11-16 — AFRE Wave 2, V9.2 Collectors, V7/V7.1 Audit & Dynamic COM Discovery
- **Ghidra 12.1.4 & V9.2 Collectors:** Completed deterministic extraction on `HFD_Code_V2.3.bin` (`313,652` bytes, SHA-256 `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03`) and validated `V92ComputedCallCollector`, `V92SharedStateCollector`, and `V92BoundaryCollector` (checkpoint `d42f6f1`).
- **CFG V7/V7.1 Audit:** Corrected function-level graph accounting (`118` recovered functions, `42` zero-incoming roots, `368` unresolved source sites, `0` aligned LE32 pointers to `0x600315D0`).
- **Windows COM Discovery:** Added fail-closed `src/aula_bridge/windows_com_discovery.py` and `tests/test_windows_com_discovery.py` (`82` tests passing), removing hard-coded `COM8` fallback.

---

### 2026-11-15 — Raw Input Attribution, Companion Opt-In & CFG V1–V6 / JMPI Checkpoints
- **Windows Bridge & Companion:** Verified physical Raw Input attribution (`VID_0C45&PID_800A&MI_00`, NumPad 1 `vkey 0x61` / `make_code 0x4F`), bounded `CompanionDispatchWorker` (FIFO capacity 8, hold/secondary_hold suppression), and RGB565 exporter (`524b0dcd866d1554586e599b9767e06f6e8ab56eff728baae43e17684c58d304`; `1,102` tests + `67` subtests passing).
- **MCore CFG V1–V6 & JMPI:** Repaired call-graph extraction (`584` edges, canonical `0x600315D0 -> 0x60049D98`), validated standalone JMPI literal-pool post-processor (`49` literal targets, `8b0b47a5...`), reconciled queue accounting (`59696c1c...`), and ran bounded experiments up to `12288/1536` (`9c120415...`).
- **Offline Research Sync:** Synchronized `docs/SCREEN_CONTROL_EVIDENCE_INVENTORY.md` and offline codec/classifier utilities (`13b1ff06...`).

---

## Released Versions

### [v0.6.3] - 2026-11-10
- Established Chinese AULA L99 `1.0.1.4` (`212` files) and `DeviceDriver.exe` (`DD9C934E2F6F1CC53AE4AFB5B412C3F696CD4D329A03DF28BD151DAB90B3E6B3`) process hierarchy (`L99_中文_V1.31.exe` for keyboard `0C45:800A` vs `L99_ISP_中文完整UI_V1.23_156.exe` for screen `EEEF:268A`).
- Documented `Flash.ini` SPI flash database, Enigma Virtual Box `evb*.tmp` stubs, and corrected `UartTFT-II_Flash.bin` (`127,599,044` bytes, SHA-256 `4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4`) provenance as an official AULA website download.

### [v0.6.2] - 2026-11-10
- Verified `DeviceDriver.exe` parent-child process creation tree via Process Monitor without initiating firmware flashing.

### [v0.6.1] - 2026-11-10
- Scoped official capture toolkit exclusively to untouched `firmware\unpacked\L99 ISP V1.23.exe` (`111,008` bytes, SHA-256 `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0`); excluded Screen Reset EXE and patched binaries.

### [v0.6.0] - 2026-11-10
- Added `docs/OFFICIAL_UPDATE_CAPTURE_PLAN.md`, `scripts/prepare_official_capture.ps1`, `scripts/analyse_official_capture.py`, and synthetic unit tests `tests/test_analyse_official_capture.py`.

### [v0.5.0] - 2026-11-10
- Added `docs/VENDOR_FIRMWARE_PROVENANCE.md`, `vendor/vendor_files_manifest.json`, and UI-only package layout analysis (`96` tests passing).

### [v0.4.x – v0.2.x] - 2026-11-10 (Prior Unreleased Consolidation)
- Implemented `scripts/flash_checksum_scanner.py` (`--mode quick` / `--mode deep` with multiprocessing and caching).
- Verified Page 21 NumPad 1 descriptors `341` (`0x0077C446`) and `342` (`0x0077E758`, `67x67` ARGB4444, `8,978` bytes) and added offline working-copy patcher `scripts/patch_l99_numpad_icon.py`.
- Completed static PE analysis of `L99 ISP V1.23.exe` and `HFD_ISP_TOOL_V1.31.exe` (gates `C6–C18`).

### [v0.1.0] - 2026-11-09
- Initialized repository structure, protocol replay notes, CSV mappings (`device_mapping.csv`, `numpad_hid_mapping.csv`), dual-controller discovery (`0C45:800A` + `EEEF:268A`), `320x480` LCD findings, and factory UI inventory (`30` pages, `385` display records, `187` touch records, `1,138` icon descriptors).
## 2026-11-24 - DI-ADAPTER-A, MailboxTransport, FW-SAFE-A/B

- DI-ADAPTER-A: PASS_ADAPTER_PROTOCOL_EMULATOR 12/12. Pixel buffer VP 0x0400-0x1BFF and mailbox VP 0x1F00-0x1F04 SAFE on pages 1-40
  (LCD and fb0 identical to control). TCP bridge -> CEmu UART -> patched V2.2: A->B->C exact, page 1->21->1 resend, reconnect, invalid rect -> ERROR.
  Bridge fix: stale UART socket must not enter the control branch. Client l99_mailbox.py SHA-256 407B9942...A0A8.
- MailboxTransport (opendeck/DI-D1, commit 7f2ab65): 33 tests pass (21 original + 12 new). OPEN: slot config invented 64x64 icons at (16+76c, 96+76r);
  layout.py defines 4x4 cells of 80x120 (9600 px > 6144 buffer) and no banding test exists. Geometry fix required before live check.
- FW-SAFE-A/B: physical flash NO-GO unchanged. App embeds device descriptor EEEF:268A at 0x6000c198 (byte-identical to capture); 3 USB enumerations identical.
  Update order: 4B, 4C, 4A x150, 4E, 6F, 6C x46,619, 6E, 7E x92, 4F. Flash API 0x00800004 has one caller (0x6003fc74);
  no call-graph path from the USB opcode handlers to it; no code user of bootloader-range literals. 4B reply value not a simple function of the nonce.
  Update path owner UNDETERMINED. Bootloader image not available.
- Screen flash tools (REA aula_exe_re): L99_ISP_CNUI_V1.23_156.exe and "L99 keyboard Screen reset firmware.exe" (same code, .enigma2 section,
  contain EEEF:268A, HFD_Code, UartTFT, LT168A.. strings). Keyboard reset tools are separate (not analysed here). Do not run any of them.
- Next: FW-SAFE-C (decompile 0x60045340/0x60021090, embedded file table of the screen tools), MailboxTransport geometry fix, then OpenDeck -> CEmu live check.

### AULA-L99-HW2-PHYSICAL-HID-2026-11-24

- Product baseline remains 4 columns x 4 rows (16 OpenDeck buttons). A 4-column x 5-row (20-button) layout is a future improvement only, after first-version success. No dedicated OpenDeck entry button or page is required.
- L99 Mini Numpad is a touchscreen virtual function, not a separate physical Numpad. Preserve original keyboard behavior and the stock virtual Mini Numpad outside OpenDeck routing.
- Physical normal-mode USB capture: `C:\temp\aula-l99-capture\HW2_FINAL\HW2_FINAL_PHYSICAL_TOUCH.pcapng` (4,030,404 bytes; SHA-256 `B7677D354B837A6030BCEDB45688E0FCE7C858D79D69FBC9A2731C70EE15E8F4`). Operator action log: `HW2_ACTION_LOG.csv` (SHA-256 `E6A25740D5F559DD53DB4B9DF05FFEB1D251DACD5C37363B03DD51BE7BB3C9AF`). Both were hash-verified locally. Capture and action log are evidence, not source code and should not be committed.
- USBPcap1 enumeration identifies Bus 1 Device 15 `EEEF:268A` (screen CDC, Windows COM6 at capture time) and Bus 1 Device 16 `0C45:800A` (keyboard/HID). COM port assignments can change.
- Time-aligned Device 16 endpoint `0x82` HID reports contain 5-byte payloads beginning `06`; touchpad movement correlates with signed relative mouse deltas. Green and blue touchpad click tests produce `06 01 00 00 00` / `06 02 00 00 00`, followed by `06 00 00 00 00` release reports. These are physical capture observations, not absolute touchscreen X/Y coordinates.
- Device 16 endpoint `0x81` carries 8-byte keyboard HID reports for touchscreen virtual Mini Numpad: key usages `0x59` (1), `0x5D` (5), and `0x58` (Enter), with zeroed release reports. Preserve exact action-log and frame provenance for future decoding.
- Absolute 320x480 touch coordinates, independent 4x4 touch routing, and suppression of simultaneous Windows mouse events remain UNVERIFIED. Physical touchscreen-to-OpenDeck action path is NOT COMPLETE. Existing TOUCH-P1 33/33 offline tests do not establish physical touch transport.
- Dynamic icon baseline: DI-PATCH-A-FINAL CEmu 14/14; A2-R2 agent-reported CEmu live closure; DI-D1 geometry/banding 4x4. Patch Engine P1 agent-reported 32/32 offline with exact golden SHA `df3a998b0c8cf7689610bc2dae63f4081a660e3d6b0b927f2dd3f92acb6310fe`, 16 patch operations and 327 actual changed bytes (historical 356-byte footprint is a different measure).
- PATCH-SAFE-T1/T2: 149/149 bounded CFG instructions and modeled stack balance pass; full patch safety PARTIAL. FW-SAFE-C R4-R9 evidence closure complete. Independent bad-app recovery BLOCKED, interrupted-update recovery UNVERIFIED, physical flashing NO-GO.
- Next engineering task: use the verified relative-mouse and virtual-Numpad HID report evidence to determine an independent absolute touch event route without mouse side effects. Do not repeat USB inventory, generic firmware RE, or completed capture analysis.

## GT911-NATIVE-CONSOLIDATED-R3 | 2026-11-26

- **Emulator milestone:** `HANDLER_ENTRY_OBSERVED_CEMU` (isolated stock HFD V2.2 / official captured UI / canonical trace library). Evidence source: `/home/reauser/rea-lab/work/aula_gt911_native_consolidated_r3/output/`.
- Controlled idle: IRQ62=0, GT911 reads=0, no handler stop; final PC `0x60041D28`.
- Touch `(100,200)` and `(200,100)`: IRQ62=1 and exact pre-instruction stop at `0x6003FFD8` in both runs; GT911 reads=0. This confirms handler-entry correlation in CEmu, **not** handler execution, coordinate consumption or UI event dispatch.
- Exact stock V2.2 SHA-256: `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf`.
- Official captured UI SHA-256: `903a4fbad5ed1f6165d8b4491ef967fb2c88e375c6a416b21476cdb20a99d76d`.
- Canonical CEmu trace library SHA-256: `79a49b71665ba5f63526b1d42d09a3c9f02dd646fe1f374cd75198f3952133f6`.
- A separate modified library was present in checkpoint inventory (`31f7f4840fd76ec9c5f661ed5a9a3fbe444bc1a25989b6b8f3591e5ca4b56c0d`). Runtime case library provenance should be checked against the actual runner before any stronger conclusion.
- **Unresolved:** GT911 register reads, X/Y and DOWN/UP state, button/page dispatch, firmware queue producer, and physical Touch-to-OpenDeck. Stop-PC occurs before the first handler instruction executes.
- **Next bounded task:** GT911-HANDLER-CONTINUATION-R1, isolated CEmu only; resume from handler entry and record register reads and coordinate-dependent RAM/event changes. Do not repeat vector/zero-fill analysis.
- Dynamic icon pipeline remains `PASS_CEMU`; TOUCH-P1 remains `PASS_OFFLINE`; physical flash remains **NO-GO**. First version is 4x4 / 16 buttons; 4x5 / 20 buttons remains future HOLD.
