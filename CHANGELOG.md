## 2026-11-08 19:32 GMT - External brick incident adopted as project safety constraint

### Action performed
- Clarified that the brick incident belongs to the third-party Aula_L99_Linux author's research history.
- Confirmed that this project has not experienced a brick incident.
- Adopted the external incident as a project-level safety warning.

### Files created or changed
- CHANGELOG.md

### Commands or test method
- Reviewed the previously inspected third-party protocol.py safety implementation.
- No hardware commands were executed.
- No COM, HID, ISP, flash write, erase, or firmware update operations were performed.

### Result
- The local AULA L99 remains in its current working state.
- Third-party evidence shows that oversized writes can still be acknowledged by the panel while data continues beyond the intended flash slot.
- Known host-side safety checks can be bypassed by unknown addresses or explicit force options.

### Conclusion
- A successful ACK must never be treated as proof that a flash write is safe.
- Unknown flash addresses, arbitrary address writes, force overrides, ISP operations, and firmware writes are considered unsafe research operations.
- HFD_Code_V2.3.bin analysis remains read-only.
- The third-party brick incident is a safety warning, not an incident attributed to this project.

### Remaining follow-up
- Continue read-only analysis of the Aula_L99_Linux firmware documentation.
- Cross-reference HFD_Code_V2.3.bin against the documented flash layout and page/resource structures.
- Do not perform firmware or unknown flash writes until a repeatable full read-back, verified backup, flash layout, and independent recovery path have been established.

## 2026-11-08 19:35 GMT - Third-party panel flash table research reviewed

### Action performed
- Inspected the local Aula_L99_Linux screen reverse-engineering notes.
- Reviewed re_notes/flash_slot_table.md in full.
- Re-evaluated the next binary-analysis target using the documented panel-side firmware structures.

### Files created or changed
- CHANGELOG.md
- No firmware, capture, vendor binary, or device content was modified.

### Commands or test method
- Enumerated the local Aula_L99_Linux research directories.
- Read tools/aula_l99_screen/re_notes/flash_slot_table.md.
- No USB, COM, HID, ISP, erase, flash-write, or firmware-execution operations were performed.

### Result
- No files were returned from the expected documentation/Firmware directory.
- The relevant firmware research is present under tools/aula_l99_screen/re_notes.
- The vendor updater firmware contains six flash base addresses:
  0x04060000
  0x040C0000
  0x04120000
  0x04180000
  0x041E0000
  0x04240000
- The six bases follow a uniform 0x60000 stride.
- 0x04180000, 0x041E0000, and 0x04240000 independently match the captured background, photo-frame, and GIF upload destinations.
- 0x04200000 is not on the slot lattice and is not a partition boundary.
- The research also identified six candidate per-slot RAM descriptor or handle addresses:
  0x0081350C
  0x00813510
  0x00813514
  0x00813518
  0x0081351C
  0x00813520
- These RAM entries were not followed further by the reference project.
- The notes correct an earlier LT7689 identification and use LT168/LT168B reference material for the touchscreen controller analysis.
- The documented flash geometry strongly supports the 128 MB SPI NAND BOM option, but the exact populated flash device on this keyboard has not been directly identified.
- The exact GIF region extent remains inferred rather than directly measured.

### Conclusion
- The six-entry panel flash structure is a strong firmware-analysis anchor.
- The six 4-byte-stride RAM entries are potentially more useful for locating resource descriptors and page-management code than blind searches for screen dimensions.
- HFD_Code_V2.3.bin must not yet be assumed to be the same panel-side firmware image described by the reference project.
- Its role must first be established by checking for the documented flash table and RAM-handle constants.
- 0x04200000 remains unsuitable as a custom slot or write target.

### Remaining follow-up
- Search HFD_Code_V2.2.bin and HFD_Code_V2.3.bin read-only for the documented five-entry flash-table sequence, all six individual flash bases, and the six RAM-handle addresses.
- If the structures are present, inspect their surrounding binary context and compare V2.2 against V2.3.
- If the structures are absent, inspect embedded_lt168_firmware.md and screen_firmware_updater.md to identify and extract the actual panel-side firmware payload from the updater.
- Do not perform any unknown flash write, force override, ISP operation, erase, or modified firmware flashing.

## 2026-11-08 19:37 GMT - HFD flash-map code regions inspected

### Action performed
- Hex-inspected the documented flash-base region in HFD_Code_V2.2.bin.
- Hex-inspected the flash-base and repeated RAM-address regions in HFD_Code_V2.3.bin.
- Re-evaluated whether these locations are static tables, descriptors, or executable references.

### Files created or changed
- CHANGELOG.md
- No firmware, vendor binary, capture, or device content was modified.

### Commands or test method
- Used a read-only Python hexdump of:
  - HFD_Code_V2.2.bin offsets 0x00030980 to 0x00030AC0
  - HFD_Code_V2.3.bin offsets 0x00032790 to 0x000328D0
  - HFD_Code_V2.3.bin offsets 0x00032970 to 0x00032A10
- No USB, COM, HID, ISP, erase, flash-write, or firmware-execution operation was performed.

### Result
- The flash bases and 0x008135xx RAM addresses are embedded in regions surrounded by executable-looking machine code.
- The first V2.3 region maps the first five flash bases to the consecutive RAM addresses 0x0081350C through 0x0081351C.
- The GIF base 0x04240000 appears later in the same code region with RAM address 0x00813520.
- A second V2.3 code region references the same six RAM addresses in a non-sequential order.
- The second occurrence is therefore more consistent with a function consuming the same six slot-state objects than with a duplicate static handle array.
- The equivalent V2.2 region contains different nearby RAM addresses, including 0x008133E8, 0x00812AD0, 0x008133D8, and 0x008133D4.
- Both versions contain multiple addresses in the 0x60000000 memory range near this code.

### Conclusion
- The flash structure is implemented through executable code and immediate or literal references, not only through a simple standalone data table.
- The six 0x008135xx values in V2.3 are strong candidates for per-slot RAM state objects or handles.
- V2.2 likely has corresponding state objects at different linked RAM addresses; the earlier zero-hit result only shows that it does not use the exact V2.3 addresses.
- The V2.3 file-size increase and table displacement remain exactly 0x1E18, but the surrounding code is not proven to be a byte-identical relocation.
- V2.2 and V2.3 appear to have been rebuilt or relinked, changing RAM and 0x60000000-range addresses.
- The CPU architecture and image load mapping must be established before attempting disassembly or function cross-references.

### Remaining follow-up
- Inspect embedded_lt168_firmware.md and screen_firmware_updater.md for the CPU architecture, instruction encoding, image load base, entry point, and file-offset mapping.
- Establish the correct disassembler configuration.
- Map V2.3 file offsets to runtime addresses.
- Disassemble the functions referencing the six slot-state objects.
- Trace those consumers toward resource loading, page descriptors, widget routing, and the built-in NumPad page.
- Keep all firmware writes, ISP operations, force overrides, unknown address writes, and erase operations blocked.

## 2026-11-08 19:39 GMT - HFD V2.2 to V2.3 structural comparison completed

### Action performed
- Performed a read-only multi-resolution block comparison between HFD_Code_V2.2.bin and HFD_Code_V2.3.bin.
- Tested unique matching blocks at 16, 32, 64, 128, and 256-byte granularities.

### Files created or changed
- CHANGELOG.md
- No firmware or device content was modified.

### Commands or test method
- Indexed SHA-256 hashes of aligned blocks from both firmware versions.
- Identified unique byte-identical blocks and contiguous matching runs.
- Compared file-offset displacement across matching regions.
- No USB, COM, HID, ISP, erase, flash-write, or firmware-execution operation was performed.

### Result
- Large byte-identical regions remain at identical offsets in the early firmware.
- A 128-byte block comparison found a byte-identical 0x4280-byte run beginning at offset 0x2180 in both versions.
- A 256-byte comparison independently found a 0x4200-byte identical run beginning near offset 0x2200.
- Later matching regions do not share one uniform displacement.
- Significant observed displacement bands include:
  - 0x00000000
  - -0x00000170
  - +0x00001D40
  - +0x00001E50
  - +0x00001E80
- Several substantial later regions use a +0x1E80 displacement.
- The total file-size difference remains +0x1E18.
- The +0x1E80 dominant later displacement differs from the total size growth by 0x68 bytes.

### Conclusion
- HFD_Code_V2.3.bin is not HFD_Code_V2.2.bin with one simple 0x1E18-byte insertion.
- The firmware contains multiple changed, inserted, deleted, or relinked regions.
- The earlier observation that the flash-table displacement matched the total file-size increase is insufficient to establish a single inserted feature region and is superseded by the broader comparison.
- Large unchanged regions show that the versions are still structurally related, making cross-version signature correlation practical.
- Searching for a single 7.7 KB V2.3 feature block is not the preferred next path.

### Remaining follow-up
- Begin read-only signature analysis for the independently verified 17 NumPad HID usage values.
- Search full, row-level, and 1/2/4-byte-width representations in both HFD firmware versions.
- If direct sequences are absent, perform proximity and fixed-stride analysis for descriptor-style encodings.
- Correlate any candidate action structure with nearby page, visual-resource, coordinate, and flash references.
- Keep all firmware writes, ISP operations, unknown address writes, force overrides, and erase operations blocked.

## 2026-11-08 19:40 GMT - Direct NumPad HID signature search completed

### Action performed
- Searched HFD_Code_V2.2.bin and HFD_Code_V2.3.bin for the complete verified 17-key NumPad HID sequence and multiple row-level subsets.
- Tested 8-bit, 16-bit little-endian, and 32-bit little-endian representations.

### Files created or changed
- CHANGELOG.md
- No firmware or device content was modified.

### Commands or test method
- Performed read-only byte-pattern searches against both HFD firmware images.
- Searched the full 17-key sequence and the following subsets:
  - 53 54 55 56
  - 5F 60 61 57
  - 5C 5D 5E
  - 59 5A 5B
  - 58 62 63
- No USB, COM, HID, ISP, erase, flash-write, or firmware-execution operation was performed.

### Result
- No complete 17-key NumPad usage sequence was found in either firmware image.
- No 16-bit or 32-bit representation of any tested sequence was found.
- The functional NumPad row subsets were not found.
- A single 8-bit match for 53 54 55 56 was found in each firmware:
  - V2.2 at 0x00006FDC
  - V2.3 at 0x00006E70
- Both matches occur inside the ASCII sequence containing Q R S T U V W X Y Z and are confirmed false positives unrelated to the NumPad.

### Conclusion
- There is currently no evidence that the standard USB HID NumPad usage values are stored directly as a contiguous action table in the LT168B HFD firmware.
- Continuing simple HID-byte signature searches in HFD_Code has low expected value.
- A plausible architecture is that LT168B page/touch logic produces an internal page/action event which is translated elsewhere into the final 0C45:800A HID report.
- This remains an architectural hypothesis rather than a verified event-routing mechanism.
- Analysis should now target the built-in NumPad UI/page representation itself: page identifiers, resources, touch rectangles, action IDs, and rendering structures.

### Remaining follow-up
- Search the local Aula_L99_Linux research tree for existing work on NumPad, keypad, widgets, pages, touch coordinates, resources, bitmaps, icons, and UI structures.
- Avoid repeating any built-in UI research already completed by the reference project.
- If no relevant prior work exists, begin read-only coordinate and descriptor-structure analysis of HFD_Code_V2.2.bin and HFD_Code_V2.3.bin.
- Keep all firmware writes, ISP operations, unknown address writes, force overrides, and erase operations blocked.

## 2026-11-08 19:42 GMT - Third-party built-in UI research search completed

### Action performed
- Performed a narrowed search of the local Aula_L99_Linux research tree for NumPad, keypad, calculator, touch-zone, page-ID, page-table, and built-in-page research.
- Reviewed the resulting candidate hits.

### Files created or changed
- capture_analysis/aula_reference_builtin_ui_hits.txt
- CHANGELOG.md
- No firmware, capture, vendor binary, or device content was modified.

### Commands or test method
- Searched Markdown, Python, and text files in the local third-party research tree.
- Restricted patterns to terms directly relevant to built-in page and touch-zone structures.
- No USB, COM, HID, ISP, erase, flash-write, or firmware-execution operation was performed.

### Result
- The narrowed result file is 3760 bytes.
- No direct third-party research on the built-in touchscreen NumPad page, calculator page, page IDs, page tables, or touch-zone descriptors was identified in the returned results.
- NumPad-related matches occur in tools/aula_l99_hacky/protocol.py and describe PC-side USB HID usage-name resolution.
- These entries include standard NumPad usages such as NumLock 0x53, Divide 0x54, Multiply 0x55, Subtract 0x56, Add 0x57, Enter 0x58, NumPad0 0x62, and Decimal 0x63.
- These HID usage-name definitions are not evidence of an LT168B touchscreen NumPad page descriptor.

### Conclusion
- Existing Aula_L99_Linux research does not appear to have already solved the built-in NumPad page/resource/touch-zone structure in the narrowed search results.
- The PC-side HID mapping does not provide a useful direct signature for locating the touchscreen page in the HFD firmware.
- Before blind coordinate scanning of the proprietary LT168B firmware, the existing NumPad and calculator captures should be compared at the 1A86:8091 endpoint 0x83 UI-report layer.
- This may reveal an intermediate page or action identifier that can later be used as a stronger firmware signature.

### Remaining follow-up
- Inspect existing analyze_aula_captures.py support for 21-byte UI/touch reports and endpoint 0x83.
- Locate already-generated NumPad and calculator analysis outputs.
- If suitable packet dumps already exist, compare them directly without recapturing USB traffic.
- Otherwise extract only the relevant endpoint 0x83 reports from the existing PCAPNG files.
- Keep all firmware writes, ISP operations, unknown address writes, force overrides, and erase operations blocked.

## 2026-11-08 19:44 GMT - Existing NumPad raw USB analysis data verified

### Action performed
- Inspected the existing aula_numpad_all_keys analysis output and the analyzer raw-payload export implementation.

### Files created or changed
- CHANGELOG.md
- No capture, firmware, vendor binary, or device content was modified.

### Commands or test method
- Enumerated the files under capture_analysis/aula_numpad_all_keys.
- Inspected analyze_aula_captures.py around the all_payloads.csv export path.
- No USB recapture or hardware operation was performed.

### Result
- The existing NumPad analysis contains all_payloads.csv with 408422 bytes of captured payload data.
- keyboard_reports.csv, mouse_reports.csv, touch_reports.csv, endpoint and timing summaries are also already available.
- all_payloads.csv preserves frame number, timestamp, device, endpoint, frame length, data length, and complete payload.
- This is sufficient to correlate each verified NumPad HID press against all USB-visible activity without repeating the capture.

### Conclusion
- No new USB capture is required for the next correlation step.
- The 17 verified NumPad keyboard-press timestamps can be used as anchors against all_payloads.csv.
- A narrow +/-20 ms window will be used to test for a consistent non-keyboard USB precursor associated with each NumPad touch action.

### Remaining follow-up
- Correlate all 17 NumPad HID press events against all USB payloads within +/-20 ms.
- Identify any device/endpoint/payload pattern that consistently precedes the HID event.
- If no USB-visible precursor exists, stop pursuing the USB-routing hypothesis and return to read-only LT168B built-in page/resource analysis.
- Keep all firmware, ISP, erase, force-override, and unknown flash operations blocked.

## 2026-11-08 19:49 GMT - LT168B UI ASCII anchor search completed

### Action performed
- Searched HFD_Code_V2.2.bin and HFD_Code_V2.3.bin for readable ASCII strings related to built-in page and visual-resource functionality.

### Files created or changed
- CHANGELOG.md
- No firmware or device content was modified.

### Commands or test method
- Performed a read-only ASCII string scan of both HFD firmware images.
- Filtered strings using terms related to NumPad, keys, calculator, touch, pages, menus, widgets, icons, bitmaps, images, photos, and GIF handling.
- The keyboard remained disconnected and no hardware communication was performed.

### Result
- HFD_Code_V2.2.bin produced no matching ASCII strings.
- HFD_Code_V2.3.bin produced no matching ASCII strings.
- No direct readable NumPad, calculator, page, menu, widget, icon, or comparable UI text anchor was identified using this method.

### Conclusion
- Readable UI strings do not currently provide a useful route to the built-in NumPad page implementation.
- Additional broad ASCII keyword searching has low expected value.
- The next static-analysis target should be binary page or geometry descriptor structures rather than text or final USB HID usages.

### Remaining follow-up
- Perform read-only 17-entry descriptor hunting across both HFD firmware builds.
- Prioritize repeated structures containing plausible 320x480 screen coordinates.
- Test common descriptor strides while rejecting zero-filled and constant-data false positives.
- Cross-correlate candidates between V2.2 and V2.3 before interpreting any structure as a page definition.
- Keep the keyboard unplugged for this offline analysis.
- Keep all firmware writes, ISP operations, unknown address writes, force overrides, and erase operations blocked.

## 2026-11-08 20:10 GMT - ISP flash database and flash verification strings identified

### Action performed
- Decoded Flash.ini and inspected HFD_ISP_TOOL_V1.31.exe around its firmware paths, update messages, CRC strings, and file-read errors.
- Distinguished local file reads from device flash verification behavior.

### Files created or changed
- CHANGELOG.md
- No firmware, flash image, capture, vendor binary, or device content was modified.

### Commands or test method
- Read Flash.ini in multiple text encodings.
- Calculated its size and SHA-256 hash.
- Inspected ASCII strings and binary context in HFD_ISP_TOOL_V1.31.exe.
- The keyboard remained disconnected.
- No USB, COM, HID, ISP, erase, flash-write, firmware-execution, or device-read command was performed.

### Result
- Flash.ini is a cleartext JEDEC flash-device database.
- Flash.ini size is 1571 bytes.
- Flash.ini SHA-256 is e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c.
- The database includes NOR devices and SPI NAND devices.
- 128 MiB SPI NAND entries use a 2048-byte page size and 65536 pages, including W25N01GV, W25N01KV, GD5F1GM7UE, GD5F1GQ4UB, XT26G01 variants, and other 1-Gbit parts.
- The exact flash device populated in this AULA L99 remains unverified because no live JEDEC ID has been obtained.
- HFD_ISP_TOOL_V1.31.exe size is 99328 bytes.
- Its SHA-256 is 3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282.
- The ISP tool contains paths for HFD_Code_V2.3.bin, HFD_Code_V2.2.bin, and UartTFT-II_Flash.bin.
- The ISP tool contains FileCRC, FlashCRC, length, update-success, and update-failure messages.
- This provides evidence of a post-write flash verification or CRC-comparison step.
- The tool's Read fail, please check the path message is associated with local firmware file paths and is not evidence of arbitrary device-flash read-back.
- No arbitrary external-NAND byte read or dump function has been identified.

### Conclusion
- UartTFT-II_Flash.bin is a distinct ISP update input and is a strong candidate for a full external-flash or resource image.
- The ISP tool likely verifies a written image using a device-side or device-reported flash CRC.
- CRC verification capability does not establish arbitrary flash-byte read-back.
- Flash.ini supports the 128 MiB SPI NAND architecture but does not prove which supported chip is populated in the local keyboard.
- Full-flash backup and recovery remain unresolved, so firmware and resource writes remain blocked.

### Remaining follow-up
- Map the ISP tool's PE sections and string virtual addresses.
- Cross-reference FileCRC and FlashCRC strings in the x86 executable.
- Identify the command and packet construction used to obtain FlashCRC.
- Determine whether verification supports arbitrary address and length ranges or only a fixed post-update image CRC.
- Search for an embedded or nested UartTFT-II_Flash.bin without executing the ISP tool.
- Keep the keyboard unplugged during offline analysis.

## 2026-11-08 20:15 GMT - Device-reported flash CRC verification path confirmed

### Action performed
- Disassembled the HFD ISP tool's CRC calculation, response-field extraction, CRC display, and completion-state code.
- Traced object fields used for file CRC, flash CRC, image length, and data buffers.

### Files created or changed
- .gitignore
- capture_analysis/hfd_isp_crc_verify_disassembly.txt
- capture_analysis/hfd_isp_object_field_xrefs.txt
- capture_analysis/hfd_isp_crc_dataflow.txt
- CHANGELOG.md
- A local .venv-analysis directory was created and excluded through .gitignore.
- No firmware, flash image, vendor executable, capture, or device content was modified.

### Commands or test method
- Created a project-local Python analysis environment containing pefile and capstone.
- Disassembled the standard x86 PE32 HFD_ISP_TOOL_V1.31.exe.
- Traced accesses to object fields at offsets 0xF4, 0xFC, 0x100, 0x104, and 0x110.
- The keyboard remained disconnected.
- No USB, COM, HID, ISP, erase, flash-write, firmware execution, or live device-read command was performed.

### Result
- The ISP tool computes a table-driven CRC over the host-side input buffer.
- The CRC lookup table is located at virtual address 0x0040F500.
- The host-computed file CRC is stored at object offset 0x100.
- The firmware/image length is stored at object offset 0xF4.
- The input data-buffer pointer is stored at object offset 0x110.
- A separate 32-bit value is assembled from response-buffer bytes at offsets 0x174 through 0x177 and stored at object offset 0x104.
- The ISP tool later formats object offset 0x104 using the FlashCRC label.
- The tool also formats the image length using object offset 0xF4.
- Response-buffer bytes 0x178 through 0x17F are also consumed, showing that this is part of a larger returned status or metadata structure.
- The evidence strongly supports a device-reported flash CRC or equivalent post-write integrity value rather than a second host-only CRC calculation.

### Conclusion
- HFD_ISP_TOOL_V1.31.exe implements post-write integrity verification using a host-computed FileCRC and a separately received FlashCRC.
- This is evidence of a device-side or device-reported CRC verification mechanism.
- It is not evidence of arbitrary flash-byte read-back or a full external-NAND dump function.
- The CRC mechanism must not be tested live until its command semantics, address and length handling, and non-destructive behavior are established statically.
- Firmware, ISP, erase, and unknown flash operations remain blocked.

### Remaining follow-up
- Trace the origin and parser for the response buffer containing bytes 0x174 through 0x17F.
- Identify all reads and comparisons of object fields 0x100 and 0x104.
- Determine whether FileCRC and FlashCRC are directly compared and where the success or failure branch occurs.
- Identify the ISP command that requests or returns FlashCRC.
- Determine whether the CRC command supports arbitrary address and length ranges or only verifies a fixed post-update image.
- Continue offline analysis with the keyboard unplugged.
## 2026-11-09 19:59 GMT - Factory screen image extracted and Mini Numpad page mapped
### Action performed
- Cloned the softce/aula-l99-research repository for offline reference and inspection.
- Downloaded the official AULA L99 reset firmware package dated 2026.5.25 from the manufacturer source.
- Verified the reset ZIP before processing.
- Used the repository's hash-locked offline extractor to recover the factory screen resource image and both HFD firmware binaries.
- Ran the offline UI inspector against the verified factory UartTFT-II_Flash.bin.
- Identified page 21 as the factory Mini Numpad page.
- Mapped all 17 touch actions, button rectangles, return codes, and normal/pressed icon descriptors.
- No hardware, USB, COM, updater, or flash operation was performed.
### Files created or obtained locally
- tools/softce-aula-l99-research/input/L99-reset.zip
- tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin
- tools/softce-aula-l99-research/extracted/HFD_Code_V2.2.bin
- tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin
- tools/softce-aula-l99-research/inspection/manifest.json
- tools/softce-aula-l99-research/inspection/touch_zones.csv
- tools/softce-aula-l99-research/inspection/page21_summary.json
- tools/softce-aula-l99-research/inspection/pages/page_21_bank0.png
- tools/softce-aula-l99-research/inspection/pages/page_21_bank1.png
- tools/softce-aula-l99-research/inspection/assets/
- tools/softce-aula-l99-research/.venv/
- CHANGELOG.md
### Verified official reset package
- Reset ZIP size: 45080624 bytes.
- Reset ZIP SHA-256: e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3.
- The downloaded ZIP exactly matched the size and SHA-256 documented by the research repository.
### Verified extracted payloads
- UartTFT-II_Flash.bin size: 127599044 bytes.
- UartTFT-II_Flash.bin SHA-256: 4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4.
- HFD_Code_V2.2.bin size: 305800 bytes.
- HFD_Code_V2.2.bin SHA-256: 432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf.
- HFD_Code_V2.3.bin size: 313652 bytes.
- HFD_Code_V2.3.bin SHA-256: a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03.
- The recovered HFD_Code_V2.3.bin differs from an earlier same-named V2.3 build, confirming that filenames alone are insufficient for firmware identification.
### Inspector result
- Source image: UartTFT-II_Flash.bin.
- Pages: 30.
- Display records: 385.
- Touch records: 187.
- Icon descriptors: 1138.
- Unique decoded images: 811.
- Animations: 3.
- Animation frames: 134.
- The inspector generated decoded page previews, assets, manifest metadata, and touch-zone records.
- The manifest records 26 decode issues in the wider factory image, primarily invalid-bounds descriptor candidates.
- No separate decode-issue file was generated.
- Page 21 rendered successfully and the Mini Numpad records involved in the current investigation were decoded.
### Page 21 identification
- Page 21 is visually confirmed as the factory Mini Numpad page.
- It contains 11 display records and 18 touch records.
- One touch record is the Home/back navigation region.
- Seventeen touch records are NumPad action regions.
- The Home/back record uses return value 0x0020 and transitions to page 1.
- All NumPad action records use type 0xC001 and do not change page.
- Their goto-page value is 65535.
### Complete Mini Numpad command map
- 0x0030: Num, rectangle [13,115,79,181], icons 319/320.
- 0x0031: Divide, rectangle [89,115,155,181], icons 321/322.
- 0x0032: Multiply, rectangle [165,115,231,181], icons 323/324.
- 0x0033: Minus, rectangle [243,115,309,181], icons 325/326.
- 0x0034: NumPad 7, rectangle [13,190,79,256], icons 327/328.
- 0x0035: NumPad 8, rectangle [89,190,155,256], icons 329/330.
- 0x0036: NumPad 9, rectangle [165,190,231,256], icons 331/332.
- 0x0037: Plus, rectangle [243,190,309,327], icons 333/334.
- 0x0038: NumPad 4, rectangle [13,263,79,329], icons 335/336.
- 0x0039: NumPad 5, rectangle [89,263,155,329], icons 337/338.
- 0x003A: NumPad 6, rectangle [165,263,231,329], icons 339/340.
- 0x003B: NumPad 1, rectangle [13,337,79,403], icons 341/342.
- 0x003C: NumPad 2, rectangle [89,337,155,403], icons 343/344.
- 0x003D: NumPad 3, rectangle [165,337,231,403], icons 345/346.
- 0x003E: Enter, rectangle [243,337,309,474], icons 351/352.
- 0x003F: NumPad 0, rectangle [13,407,150,473], icons 347/348.
- 0x0040: Decimal/Delete, rectangle [165,407,231,473], icons 349/350.
### Icon descriptor result
- The 17 buttons use 34 normal/pressed icon descriptors.
- Descriptor IDs cover decimal 319 through 352.
- The equivalent hexadecimal range is 0x013F through 0x0160.
- Each touch record directly identifies its unpressed and pressed icon descriptors.
- This confirms the mapping from a touch command to its visual normal and pressed states.
### Conclusion
- The factory screen-resource image has been obtained and independently hash-verified.
- The original Mini Numpad page no longer needs to be inferred from HFD executable code.
- Page 21, all 17 touch zones, action return codes, visual geometry, and normal/pressed descriptor pairs are now known.
- The project has moved from speculative firmware archaeology to deterministic resource-level UI analysis.
- A Stream Deck-style reskin can preserve the existing 17 hardware touch actions and replace their visual resources.
- The first modification should remain an offline single-button experiment against a separate working copy.
- The factory UartTFT-II_Flash.bin must remain unchanged as the master reference.
### Safety status
- No keyboard was connected during extraction or inspection.
- No EXE was launched.
- No official updater was executed.
- No USB or COM interface was opened.
- No firmware or screen resource was written to hardware.
- No factory BIN was modified.
- Firmware flashing remains blocked until a separately validated working image, diff, size check, and recovery procedure are ready.
### Remaining follow-up
- Resolve descriptor IDs 319 through 352 to their exact descriptor-table offsets, source addresses, dimensions, formats, allocation sizes, and decoded PNG files.
- Compare page_21_bank0.png and page_21_bank1.png.
- Select one standard 66-by-66 button for the first offline replacement.
- Prefer return code 0x003B, NumPad 1, using descriptors 341 and 342.
- Create a separate working copy of UartTFT-II_Flash.bin.
- Preserve all touch records, return codes, rectangles, transitions, and executable firmware.
- Generate a replacement normal and pressed icon using the original dimensions and encoding format.
- Ensure the encoded replacement does not exceed the original allocation.
- Re-run the inspector against the working copy.
- Produce a byte-level diff and verify that only the intended descriptor and asset data changed.
- Do not flash the modified image until recovery and restore behavior have been reviewed.
