# AULA L99 Touchscreen Reverse Engineering and Stream Deck Bridge

Windows-oriented research and tooling for turning the AULA L99 keyboard touchscreen into a Stream Deck-style controller.

## Project status

This is an active reverse-engineering and prototyping project. The present milestone is:

- Factory screen resource image extracted from an official AULA reset package.
- UartTFT-II_Flash.bin independently verified by size and SHA-256.
- Factory UI parsed successfully.
- Page 21 confirmed as the built-in Mini Numpad.
- All 17 touch zones, return codes, rectangles, and normal/pressed icon descriptor pairs mapped.
- No modified resource image has been flashed.
- Current hardware-write status remains blocked pending offline patch validation and recovery review.

## Goal

- Turn the AULA L99 320x480 touchscreen into a Stream Deck-style controller.
- Preserve the stock touch-to-keyboard logic where practical.
- Replace or redesign the built-in Mini Numpad page with custom visual controls.
- Use a Windows background bridge to map existing NumPad events to PC actions.
- Later support short dynamic status fields through safe runtime RAM updates.

## Hardware architecture

Two controllers drive the device:

Keyboard side:
- USB HID controller: VID 0C45, PID 800A in wired mode.
- Standard keyboard HID events.
- Physical keyboard, lighting, wireless modes, and screen-to-keyboard event forwarding.
- Three-mode keyboard behavior includes wired, 2.4 GHz, and Bluetooth.
- The exact version source shown on the About page remains unresolved and must not be assumed to be the screen firmware version.

Screen side:
- USB device: VID EEEF, PID 268A.
- Windows CDC/serial interface, typically exposed as a COM port.
- 320x480 touchscreen.
- Built-in local page and resource engine.
- LT168-family controller firmware.
- HFD executable images disassemble as little-endian M*Core according to the external research reproduced by this project.

Keyboard events and screen runtime updates use different transport paths.

## Verified firmware components

1. HFD_Code_V2.2.bin and HFD_Code_V2.3.bin — Screen MCU executable logic.
2. UartTFT-II_Flash.bin — Screen pages, images, descriptors, touch records, animations, and transitions.
3. Keyboard MCU firmware — Separate from the screen MCU and screen resource image.

Verified factory reset payloads:

Official reset ZIP:
- Size: 45080624 bytes
- SHA-256: e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3

UartTFT-II_Flash.bin:
- Size: 127599044 bytes
- SHA-256: 4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4

HFD_Code_V2.2.bin:
- Size: 305800 bytes
- SHA-256: 432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf

HFD_Code_V2.3.bin:
- Size: 313652 bytes
- SHA-256: a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03

Same-named firmware files may contain different builds and must be identified by hash, not filename.

Do not redistribute these vendor files.

## Factory UI inspection

- 30 pages
- 385 display records
- 187 touch records
- 1138 icon descriptors
- 811 unique decoded images
- 3 animations
- 134 animation frames
- 26 wider-image decode issues recorded in the manifest, primarily invalid-bounds descriptor candidates
- Page 21 rendered successfully

## Mini Numpad mapping

Page 21 has 11 display records and 18 touch records. Seventeen are type 0xC001 action records. One is a type 0x8001 Home/back navigation record.

Home/back uses return value 0x0020 and goto page 1. NumPad action goto_page is 65535. Descriptor range is decimal 319 through 352, hexadecimal 0x013F through 0x0160.

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

## Image upload protocol

The obsolete claim that images are standard JPEG buffers with a 64-byte header is removed.

Verified information:
- Official captured photo upload contains 154 logical chunks.
- 150 chunks are 2060-byte data packets.
- Four are short control or commit commands.
- Total captured stream is approximately 309071 bytes.
- The image payload is not standard JPEG.
- Upload and built-in UI resources are separate paths.
- Normal image upload targets photo/background/GIF flash regions and does not overlay the active Mini Numpad page.
- The screen acknowledges packet transfers, but ACK does not prove address safety.

Known risk:
- Oversized writes can be acknowledged and still overwrite adjacent flash content.
- Unknown addresses, force overrides, and raw write replay remain unsafe.
- Do not claim later third-party guards make writing completely safe.

## Upload performance

Official application:
- Approximately 1.205 seconds.
- 150 x 2060-byte USB Bulk OUT transfers.

Current Python replay:
- Stable verified run: 41.616 seconds with 151 ACKs.
- Slower baseline: 67.708 seconds with 150 ACKs.

Root cause:
- Current replay splits each 2060-byte logical packet into approximately 33 synchronous 64-byte pyserial writes.
- Each 64-byte write is artificially paced.
- This transport architecture cannot approach official speed.
- The 115200 CDC line-coding value is not a reliable physical throughput limit for this USB bulk implementation.

Next transport milestone:
- Implement scripts/replay_captured_screen_win32.py.
- Use native Windows overlapped I/O.
- Submit complete 2060-byte logical packets.
- Read acknowledgements asynchronously.
- Do not change the installed USB driver.
- Do not use Zadig, WinUSB, or libusbK in the first implementation.
- On any write timeout, stop and require a device power cycle before another live test.

## Safety policy

- Original vendor images are immutable local references.
- No firmware write from this repository should be treated as safe by default.
- No unknown flash addresses.
- No force mode.
- No arbitrary erase/write replay.
- No firmware update during extraction or inspection.
- No claim of universal brick recovery.
- The official reset package is not a raw NAND dump.
- It does not include verified per-device OOB, ECC, bad-block, calibration, or unique-board data.
- About-page V1.31 is an unresolved whole-device display version and must not be assumed to identify the screen resource image, HFD image, or PC updater.

## Tooling: read-only descriptor inspector

`scripts/inspect_l99_descriptor.py` is a read-only, offline descriptor-mapping tool for the factory
AULA L99 screen resource image (`UartTFT-II_Flash.bin`). It never opens USB, COM, or HID, never
imports serial/USB/HID/updater modules, and never modifies the source image.

It resolves a descriptor (or a Page 21 touch return code) to its source offset, format, dimensions,
encoded allocation, references, and decoded PNG, then classifies every finding as Verified, Inferred,
or Unknown. Patch feasibility is reported as `PROVEN_FOR_OFFLINE_WORKING_COPY`, `UNRESOLVED`, or
`REJECTED`.

Placeholder usage (page / return-code mode; does not imply vendor images are included):

    python scripts/inspect_l99_descriptor.py `
        --image <path-to-UartTFT-II_Flash.bin> `
        --manifest <path-to-manifest.json> `
        --page 21 `
        --return-code 0x003B `
        --output <empty-output-directory>

Direct descriptor mode:

    python scripts/inspect_l99_descriptor.py `
        --image <path> `
        --manifest <path> `
        --descriptor 341 `
        --descriptor 342 `
        --output <empty-output-directory>

See `tests/test_inspect_l99_descriptor.py` for synthetic-test coverage (no vendor firmware embedded).

## Repository contents

Only files tracked by Git are described here. Local ignored vendor binaries are not included.

Tracked: scripts, analysis tools, protocol notes, changelog, and handover documentation.

Local and ignored only: official firmware, captures, dumps, decoded assets, reset ZIPs, and third-party repositories.

## Current roadmap

1. Consolidate documentation.
2. Resolve descriptor 341/342 to source offsets, formats, dimensions, and allocations.
3. Build an offline-only single-button patcher.
4. Patch a working copy only.
5. Re-run independent inspection and byte-level diff.
6. Preserve all Page 21 touch records and screen commands.
7. Implement native Win32 overlapped uploader.
8. Validate recovery and package compatibility.
9. Only then consider a controlled hardware write.

## Attribution

- softce/aula-l99-research for the verified factory reset extraction offsets, hash-locked extractor, UI parser, page/resource research, and demonstrated custom UI approach.
- gavindi/Aula_L99_Linux for extensive keyboard and screen protocol research, Linux tools, captures, and upload format work.
- mos9527/evbunpack for Enigma Virtual Box extraction work.

Do not imply that third-party firmware or artwork is licensed by this repository.
