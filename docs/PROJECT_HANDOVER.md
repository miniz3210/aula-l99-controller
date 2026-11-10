# AULA L99 Project Handover

Continue this project from the verified state below. Do not restart the reverse engineering from scratch and do not repeat tests already marked verified.

## 1. Mission

Turn the AULA L99 keyboard's built-in 320x480 touchscreen into a Stream Deck-style controller: custom icons, multiple independent touch zones, PC-side actions, and dynamic status fields, while preserving the stock touch-to-keyboard logic where practical.

## 2. Current repository state

- Main repository path: C:\temp\aula-l99-controller
- Branch: main
- Remote: miniz3210/aula-l99-controller.git
- Current published release: v0.1.1
- HEAD commit: 516e3c82cdbe6c95c10ef8a92d3d7764013192d9
- Local ignored research directory: tools/softce-aula-l99-research
- Vendor binaries and extracted artifacts are local only and ignored by Git.

## 3. Verified hardware architecture

Keyboard side:
- USB HID controller: VID 0C45, PID 800A in wired mode.
- Standard keyboard HID events.
- Physical keyboard, lighting, wireless modes, and screen-to-keyboard event forwarding.
- Three-mode behavior: wired, 2.4 GHz, Bluetooth.
- Real-time telemetry uses a 64-byte HID Feature Report on Interface 3 (SET_REPORT, wValue 0x0300).
- About-page version V1.31 source unresolved.

Screen side:
- USB device: VID EEEF, PID 268A.
- Windows CDC/serial interface, typically a COM port.
- 320x480 touchscreen.
- Built-in local page and resource engine.
- LT168-family controller firmware.
- HFD executable images disassemble as little-endian M*Core per external research.

Keyboard events and screen runtime updates use different paths.

## 4. Verified public and local artifacts

Public repository files:
- README.md, CHANGELOG.md, VERSION, .gitignore, LICENSE
- scripts/ analysis and replay tools
- docs/ handover, protocol notes, firmware package map, third-party references, and data CSVs

Local ignored artifacts:
- tools/softce-aula-l99-research/ (softce research checkout)
- Official reset ZIP (45080624 bytes, SHA-256 e854bebb...)
- UartTFT-II_Flash.bin (127599044 bytes, SHA-256 4cb3fa5c...)
- HFD_Code_V2.2.bin (305800 bytes, SHA-256 432e358c...)
- HFD_Code_V2.3.bin (verified build): 313652 bytes, SHA-256 a76806ad...
- HFD_ISP_TOOL_V1.31.exe, Flash.ini
- Captures, dumps, decoded assets, virtual environments

External third-party repositories (not vendored):
- https://github.com/softce/aula-l99-research
- https://github.com/gavindi/Aula_L99_Linux
- https://github.com/mos9527/evbunpack

Same-named firmware files may contain different builds and must be identified by hash, not filename.

## 5. Verified screen upload protocol

- Official captured photo upload contains 154 logical chunks.
- Four are short control or commit commands.
- Total captured stream is approximately 309071 bytes.
- The screen acknowledges packet transfers.
- Upload targets photo/background/GIF flash slots.
- Upload does not overlay the built-in Mini Numpad page.
- The image payload is not standard JPEG. Obsolete JPEG/64-byte-header claims are removed.
- ACK does not prove address safety.

## 6. Verified performance evidence

- Official application: approximately 1.205 seconds, 150 x 2060-byte USB Bulk OUT transfers.
- Current Python replay: stable verified run 41.616 seconds with 151 ACKs; slower baseline 67.708 seconds with 150 ACKs.
- Root cause: current replay splits each 2060-byte logical packet into approximately 33 synchronous 64-byte pyserial writes, each artificially paced.
- The 115200 CDC line-coding value is not a reliable physical throughput limit for this USB bulk implementation.
- Write timeout leaves the endpoint wedged; a device power cycle is required before another live test.
- Next transport: scripts/replay_captured_screen_win32.py with native Windows overlapped I/O, complete 2060-byte logical packets, asynchronous ACK reads, no USB driver replacement, no Zadig/WinUSB/libusbK in the first implementation.

## 7. Verified factory resource image

- Extraction source: official AULA reset package dated 2026-05-25, recovered via the softce hash-locked offline extractor.
- Verified by size and SHA-256 against the research repository documentation.
- Inspector results: 30 pages, 385 display records, 187 touch records, 1138 icon descriptors, 811 unique decoded images, 3 animations, 134 animation frames.
- Manifest records 26 wider-image decode issues, primarily invalid-bounds descriptor candidates.
- Page 21 rendered successfully as the factory Mini Numpad page.
- Limitation: this is the screen resource image, not a raw NAND dump; it does not include verified per-device OOB, ECC, bad-block, calibration, or unique-board data.

## 8. Page 21 Mini Numpad

Page 21 has 11 display records and 18 touch records. Seventeen are type 0xC001 action records; one is a type 0x8001 Home/back navigation record.

Home/back: return value 0x0020, goto page 1. NumPad actions: goto_page 65535. Descriptor range: decimal 319 through 352 (hex 0x013F through 0x0160).

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

The 17 buttons use 34 normal/pressed icon descriptors.

### 8a. Descriptor 341 / 342 mapping (verified via scripts/inspect_l99_descriptor.py)

Descriptor 341 (0x0155) — NumPad 1 unpressed:
- Icon table bank: 0
- Descriptor table base / file offset: 6433412 (0x00623114)
- Exact descriptor entry file offset: 6437504 (0x00623A80)
- Raw descriptor bytes: 46c477004300430012230002
- Descriptor entry length: 12
- Source asset logical address / file offset: 7849030 (0x0077C446) — direct file offset, no translation
- Encoded format number: 2 — ARGB4444 (raw 16-bit packed)
- Decoded dimensions: 67 x 67
- Encoded payload length: 8978 bytes
- Full encoded record length (incl. header): 8990 bytes
- Encoded range: [7849030, 7858008] (0x0077C446 .. 0x0077E758)
- Allocation: start 7849030, end 7858008, capacity 8978
- Next confirmed asset boundary: 7858008 — VERIFIED (next descriptor address == end)
- Boundary confidence: verified
- Decoded asset: inspection\assets\0077C446_67x67_f2.png
- Decoded PNG SHA-256: daddc6dc21c58d2bbd1597024113afb2b38472d14baa239af59f8fae29c0e99b
- Source encoded-byte SHA-256: 785416bcad1789248b62dfc085f477806547d5c01f747dde150f9555a2c70317
- Referencing records: 1 — page 21 touch record offset 150697, role unpressed, return 0x003B, goto_page 65535
- Shared by other pages/controls: No
- Manifest decode issues: 0

Descriptor 342 (0x0156) — NumPad 1 pressed:
- Icon table bank: 0
- Descriptor table base / file offset: 6433412 (0x00623114)
- Exact descriptor entry file offset: 6437516 (0x00623A8C)
- Raw descriptor bytes: 58e777004300430012230002
- Descriptor entry length: 12
- Source asset logical address / file offset: 7858008 (0x0077E758) — direct file offset, no translation
- Encoded format number: 2 — ARGB4444 (raw 16-bit packed)
- Decoded dimensions: 67 x 67
- Encoded payload length: 8978 bytes
- Full encoded record length (incl. header): 8990 bytes
- Encoded range: [7858008, 7866986] (0x0077E758 .. 0x00780A6A)
- Allocation: start 7858008, end 7866986, capacity 8978
- Next confirmed asset boundary: 7866986 — VERIFIED (next descriptor address == end)
- Boundary confidence: verified
- Decoded asset: inspection\assets\0077E758_67x67_f2.png
- Decoded PNG SHA-256: aef08b1f04064c2a651b9db115d019c33425d8716fe3cc2a8ec6216d36c43750
- Source encoded-byte SHA-256: 4265cf743061b87fb85479bc64df1d05d241b1aaf88ea51392f01e2781332474
- Referencing records: 1 — page 21 touch record offset 150697, role pressed, return 0x003B, goto_page 65535
- Shared by other pages/controls: No
- Manifest decode issues: 0

Patch feasibility: PROVEN_FOR_OFFLINE_WORKING_COPY (exact encoded range, exact verified allocation
boundary, established format, confirmed dimensions, single known reference, replacement-size limit =
allocation capacity 8978, no overlap with adjacent asset). Metadata/checksum implications remain
Unknown (not covered by manifest). In-place replacement is not declared safe unless all of these are
established and a working-copy patch is validated.

## 9. Version ambiguity

- Device About page displays AULA L99 V1.31.
- Source of V1.31 is not proven.
- It may be keyboard MCU, screen MCU, UI/project version, or whole-device product version.
- HFD_ISP_TOOL_V1.31.exe version must not be equated automatically with the About-page version.
- HFD_Code V2.2/V2.3 names are separate version domains.
- Firmware compatibility must be based on screen-side identifiers, hashes, layout, and official package targeting.

## 10. What has been disproved or corrected

- The image stream is not standard JPEG.
- The 115200 line-coding value is not the observed USB transfer throughput limit.
- Official upload is approximately 1.2 seconds, not 30 to 40 seconds.
- Framebuffer upload does not overlay the Mini Numpad page.
- The external 2026-05-25 reset package contains the complete known UI/resource update image.
- About-page V1.31 is not proven to be a screen firmware version.
- Acknowledgement does not establish flash address safety.
- check_upload_fits() is not a universal allowlist and can be bypassed or fail open for unknown addresses depending on the caller.
- The exact cause of the external author's bricked keyboard remains unproven.

## 11. Safety constraints

- Original vendor images are immutable local references.
- No firmware write from this repository MUST be treated as safe by default.
- NO unknown flash addresses.
- NO force mode.
- NO arbitrary erase/write replay.
- NO firmware update during extraction or inspection.
- NO claim of universal brick recovery.
- Hardware writes are BLOCKED pending offline patch validation and recovery review.
## 12. Immediate next milestone

Workstream A (offline descriptor and resource mapping) is COMPLETE. Descriptors 341/342 are resolved
to source offsets, formats, dimensions, and allocations; patch feasibility is
PROVEN_FOR_OFFLINE_WORKING_COPY.

### 12a. Offline NumPad icon patcher (scripts/patch_l99_numpad_icon.py)

Added an offline-only ARGB4444 encoder and working-copy patcher for Page 21 NumPad 1
descriptors 341 (normal) and 342 (pressed). Verified against the factory image:

- Factory UartTFT-II_Flash.bin: size 127599044, SHA-256
  4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4 — unchanged.
- Descriptor 341: offset 0x0077C446, format 2 ARGB4444, 67x67, 8978 bytes,
  allocation [7849030, 7858008], boundary verified.
- Descriptor 342: offset 0x0077E758, format 2 ARGB4444, 67x67, 8978 bytes,
  allocation [7858008, 7866986], boundary verified.
- Round-trip validation: decoding and re-encoding both factory records is byte-for-byte equal.
- No-visual-change round trip: patching with the decoded factory normal/pressed PNGs produces
  a working copy byte-for-byte identical to the factory image (same SHA-256).
- Test icon patch: exactly two asset ranges changed; Page 21 touch record 0x003B unchanged;
  descriptors 341/342 still resolve to 67x67 ARGB4444 assets; factory size/hash/timestamp unchanged.
- Synthetic tests: tests/test_patch_l99_numpad_icon.py (no vendor firmware embedded).

Next task (from the task evidence): Review recovery and package compatibility, then prepare a
controlled flash plan. Do not implement flashing in this task.

Workstream B — Win32 overlapped uploader:
- Implement scripts/replay_captured_screen_win32.py.
- Complete 2060-byte writes.
- No USB driver replacement.
- Preserve a stable pyserial fallback.

Workstream A MUST be completed before any modified firmware write. Workstream B MAY be developed
using the existing known-safe photo upload path.

## 13. Acceptance criteria

Offline patcher:
- Factory source unchanged.
- Separate output file.
- Only intended asset bytes and required metadata changed.
- No touch record changes.
- Inspector still parses Page 21.
- All 17 actions remain mapped.
- Replacement allocation is in bounds.
- SHA-256 and diff report generated.

Win32 uploader:
- Compiles or passes py_compile as applicable.
- Does not split logical packets in userland unless required by Win32.
- Preserves command ordering.
- Receives expected ACK count.
- Handles cancellation safely.
- Reports exact failing packet and offset.
- Never retries automatically after timeout.
- Requires explicit power cycle after endpoint wedge.
- Initial target under 10 seconds.
- Final target close to official 1 to 2 seconds.

## 14. Known external references

- softce/aula-l99-research — verified factory reset extraction offsets, hash-locked extractor, UI parser, page/resource research, demonstrated custom UI approach.
- gavindi/Aula_L99_Linux — extensive keyboard and screen protocol research, Linux tools, captures, upload format work; protocol baseline for general photo/GIF/RTC/audio-spectrum work.
- mos9527/evbunpack — Enigma Virtual Box extraction used to inspect the official updater container.

Neither third-party tree is committed to this project, and third-party firmware or artwork is not licensed by this repository.

## 15. Resume commands

Run each as a simple PowerShell command or a complete script block. Do not split if/else across interactive lines.

cd "C:\temp\aula-l99-controller"

git status
git branch --show-current
git remote -v
git log --oneline --decorate -5

ii tools/softce-aula-l99-research

Get-Content tools/softce-aula-l99-research/inspection/page21_summary.json

ii tools/softce-aula-l99-research/inspection/pages/page_21_bank0.png
ii tools/softce-aula-l99-research/inspection/pages/page_21_bank1.png

py -m pytest

Get-FileHash tools/softce-aula-l99-research/input/L99-reset.zip -Algorithm SHA256
Get-FileHash tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin -Algorithm SHA256
Get-FileHash tools/softce-aula-l99-research/extracted/HFD_Code_V2.2.bin -Algorithm SHA256
Get-FileHash tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin -Algorithm SHA256

cd "C:\temp\aula-l99-controller"
