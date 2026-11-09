# AULA L99 Controller / Stream Deck Project Handover

Continue this project from the current verified state. Do not restart the reverse engineering from scratch and do not repeat tests that are already marked as verified below.

## Language and working style

- Reply in Cantonese or concise technical English, matching my message.
- Be implementation-focused and evidence-based.
- Give direct PowerShell or Python steps for Windows when action is needed.
- Do not oversimplify USB, HID, serial, firmware, or binary-analysis details.
- Verify against actual files, captures, logs, hashes, or command output before making strong claims.
- If a previous assumption is contradicted by evidence, correct it immediately.
- Do not tell me to commit, version-bump, tag, or push unless I explicitly ask.
- Use English only inside code, commands, scripts, comments, file names, and technical agent prompts.
- Every important technical step, discovery, test, file change, or decision must be recorded in a CHANGELOG section before ending the response.
- For each changelog entry include:
  - date/time if known
  - action performed
  - files created or changed
  - commands or test method
  - result
  - conclusion
  - remaining follow-up
- Never perform firmware-write or destructive commands without first establishing a verified backup and recovery path.

---

# 1. Project goal

Build a custom Stream Deck-style controller using the AULA L99 keyboard’s built-in 320 x 480 touchscreen.

The desired end state is not merely keyboard macro remapping. The target experience is:

- a visible custom Stream Deck page or widget on the keyboard screen
- custom icons
- multiple independent touch zones
- PC-side actions
- dynamic states such as mute/unmute, play/pause, VPN state, build state, CPU/GPU data, or other live status
- ideally animated or multi-state icons
- wired USB operation

The first practical target is either:

1. add a new built-in widget/page, or
2. reskin and repurpose the existing numpad page while preserving its 17 touch zones.

A plain NumPad-to-macro bridge is not sufficient by itself.

---

# 2. Current project location

Local Windows project root:

C:\temp\aula-l99-controller

Public GitHub repository:

https://github.com/miniz3210/aula-l99-controller

Git branch:

main

Latest verified push completed successfully.

Latest merge commit observed:

e5fcb4e Merge GitHub initialization and keep local project files

After the successful push, Git reported:

- branch main tracks origin/main
- branch is up to date with origin/main
- nothing to commit
- working tree clean

Important: the local project contains many ignored captures, vendor assets, firmware files, dumps, virtual environments, generated payloads, and third-party source trees. Do not use `git add .`. Add files explicitly.

Safe update pattern:

cd "C:\temp\aula-l99-controller"

git status
git add -- <specific-file>
git commit -m "<description>"
git push

---

# 3. GitHub contents

The repository currently contains the cleaned public research/tooling set, including:

- .gitignore
- LICENSE
- README.md
- requirements.txt
- analyze_aula_captures.py
- list_0c45_800a.py
- monitor_l99_com.py
- docs/
- scripts/

Documentation includes:

- docs/THIRD_PARTY_REFERENCES.md
- docs/WIN32_SERIAL_REPLAY_NOTES.md
- docs/data/device_mapping.csv
- docs/data/numpad_hid_mapping.csv
- docs/data/realtime_feature_report_layout.csv

The incomplete pseudo-Python file:

scripts/replay_captured_screen_win32.py

was not valid Python. It contained only this outline:

CreateFileW("\\\\.\\COM8")
SetupComm
SetCommState
SetCommTimeouts
WriteFile with OVERLAPPED
WaitForSingleObject
ClearCommError
ReadFile

It was converted into:

docs/WIN32_SERIAL_REPLAY_NOTES.md

All remaining project Python files passed `py -m py_compile`.

---

# 4. Git ignore and prohibited public content

The following must remain local and must not be pushed to the public repository:

- .venv-evbunpack/
- tools/
- tools/Aula_L99_Linux-main/
- tools/evbunpack-main/
- firmware/
- evbunpack_output/
- evbunpack_list_test/
- hfd_inner files/directories
- isp_memory_dumps/
- isp_runtime_dump/
- capture_analysis/
- HardwareMonitor/
- qt-tool/
- skins/
- device/
- font/
- gif/
- language/
- layouts/
- USB captures
- PCAP/PCAPNG files
- memory dumps
- official firmware
- extracted vendor EXEs, DLLs, SYS files and BIN files
- generated frame/payload text files
- decoded image variants
- local benchmark logs
- test images
- Python virtual environments and caches

Do not redistribute vendor firmware or extracted proprietary binaries. It is acceptable to publish independently written analysis, file names, sizes, hashes, protocol structure, and original scripts.

---

# 5. Verified hardware architecture

The AULA L99 exposes multiple relevant USB devices:

## Screen controller

VID:PID:

EEEF:268A

Role:

- CDC/serial screen transport
- framebuffer/image transfer
- flash-slot operations
- Windows virtual COM port, previously COM8

## Keyboard HID controller

VID:PID:

0C45:800A

Role:

- normal keyboard reports
- numpad page HID reports
- 64-byte HID Feature Reports
- real-time CPU/GPU/date/weather data transport
- Interface 3 is used for the Feature Report protocol

## Touch and pointer controller

VID:PID:

1A86:8091

Observed functions:

- endpoint 0x82: 11-byte relative mouse reports
- endpoint 0x83: UI press/release reports
- touchpad/mouse page functions

## Display

Resolution:

320 x 480

---

# 6. Verified built-in numpad behavior

The built-in numpad page provides 17 distinct touch zones.

The full verified HID mapping is:

1. Num Lock: 0x53
2. NumPad Divide: 0x54
3. NumPad Multiply: 0x55
4. NumPad Minus: 0x56
5. NumPad 7: 0x5F
6. NumPad 8: 0x60
7. NumPad 9: 0x61
8. NumPad Plus: 0x57
9. NumPad 4: 0x5C
10. NumPad 5: 0x5D
11. NumPad 6: 0x5E
12. NumPad 1: 0x59
13. NumPad 2: 0x5A
14. NumPad 3: 0x5B
15. NumPad Enter: 0x58
16. NumPad 0: 0x62
17. NumPad Decimal/Delete: 0x63

Each press appears as a standard 8-byte keyboard HID report, for example:

00 00 5F 00 00 00 00 00

Release:

00 00 00 00 00 00 00 00

The five-key verification sequence:

7, 5, 1, +, Enter

produced:

0x5F, 0x5D, 0x59, 0x57, 0x58

This is a reliable basis for a Stream Deck-style page if the visual resources can be reskinned.

---

# 7. Runtime overlay result

A critical test was completed:

Test setup:

- official AULA program closed
- screen manually placed on built-in numpad page
- USB capture started
- known working COM8 framebuffer replay executed
- original numpad positions 7, 5, 1, +, Enter pressed afterward

Result:

- the numpad screen image did not change
- all five touch actions remained functional
- Notepad received 751+ and Enter correctly

Conclusion:

The normal COM8 framebuffer/photo upload path does not overlay or replace the built-in numpad UI.

The photo framebuffer/flash-slot path and the firmware-rendered built-in page system are separate display paths.

Therefore this design does not work:

enter numpad page
then upload arbitrary framebuffer
then retain touch zones under the custom image

The path forward requires locating and modifying built-in UI resources/page descriptors, or finding a currently unused page/widget/flash slot that the firmware can route to.

Do not repeat this overlay test unless a different command, slot, or page-rendering protocol has been identified.

---

# 8. Verified real-time Widget Feature Report

The real-time data page receives a 64-byte HID Feature Report through:

- device 0C45:800A
- Interface 3
- SET_REPORT
- wValue 0x0300
- 64-byte report

The update cycle occurs approximately every 5 seconds.

Observed command sequence:

04 18 ...
04 28 ...
00 01 5A [data] ... AA 55
04 02 ...

The actual telemetry payload begins:

00 01 5A

and ends:

AA 55

Verified layout:

Offset 0 to 2:
- header 00 01 5A

Offset 3:
- year minus 2000
- 0x1A means 2026

Offset 4:
- month

Offset 5:
- day

Offset 6:
- hour

Offset 7:
- minute

Offset 8:
- second

Offsets 9 to 12:
- unresolved

Offset 13:
- CPU usage percent
- verified by controlled CPU load

Offset 14:
- CPU temperature candidate
- official monitor returned zero on the test system

Offset 15:
- GPU usage percent
- verified against nvidia-smi

Offset 16:
- GPU temperature in degrees Celsius
- verified against nvidia-smi

Offsets 17 to 21:
- likely weather/environmental fields
- not yet fully mapped in this project

Offsets 22 to 61:
- observed as zero/reserved in the tested packets

Offsets 62 to 63:
- AA 55 trailer

Controlled CPU load raised offset 13 from low values to approximately 0x4D to 0x52, matching roughly 77 to 82 percent CPU usage.

Controlled GPU testing confirmed offset 15 changes with GPU usage and offset 16 follows the NVIDIA GPU temperature.

---

# 9. Hardware-monitor issue and resolution

The AULA hardware monitor initially showed fixed values such as:

- CPU 19 percent
- GPU 27 percent

The USB Feature Reports also repeatedly transmitted those same values.

Cause:

Bitdefender Antivirus Free blocked:

C:\Program Files (x86)\AULA L99\HardwareMonitor\OpenHardwareMonitorServer.sys

The detection referenced a WinRing/OpenHardwareMonitor-style low-level driver.

An antivirus exception was added for the verified official AULA hardware-monitor component. After restarting the AULA monitor chain:

OpenHardwareMonitorServer.exe ran successfully and responded.

Process path:

C:\Program Files (x86)\AULA L99\HardwareMonitor\OpenHardwareMonitorServer.exe

Afterward CPU and GPU values changed normally.

Conclusion:

The fixed telemetry was a PC-side sensor-driver issue, not a screen protocol issue.

---

# 10. Captures and analysis completed

Multiple captures were created and analyzed locally, including:

- aula_numpad_5keys.pcapng
- aula_numpad_all_keys.pcapng
- aula_calculator_all_keys.pcapng
- aula_mouse_controls.pcapng
- aula_home_all_buttons.pcapng
- aula_home_numpad_transition.pcapng
- aula_photo_touch_points.pcapng
- aula_realtime_idle_60s.pcapng
- aula_realtime_cpu_load.pcapng
- aula_realtime_cpu_load_v2.pcapng
- aula_realtime_gpu_load.pcapng
- aula_realtime_gpu_load_v3.pcapng
- aula_official_refresh.pcapng
- aula_solid_black.pcapng
- aula_solid_white.pcapng
- aula_upload_test.pcapng
- aula_numpad_framebuffer_overlay.pcapng

These captures are local and excluded from GitHub.

The batch analyzer:

analyze_aula_captures.py

extracts:

- endpoint summaries
- all USB payloads
- keyboard reports
- consumer-control candidates
- 11-byte mouse reports
- 21-byte touch/UI reports
- large screen packets
- timing summaries
- cross-capture summaries

Important compatibility note:

This Wireshark/tshark build does not support `frame_raw` as a `-T fields` field.

The working payload fallback chain uses:

- usbhid.data
- usbcom.data.out_payload
- usb.capdata

Do not reintroduce `frame_raw` into `-T fields`.

---

# 11. Image and framebuffer findings

Previous work established:

- official screen upload uses approximately 150 large packets plus short commands
- large packet data is not normal JPEG
- the payload uses a custom framebuffer/image format
- CRC-16/ARC-style validation was investigated and replayed
- custom screen uploads work for the photo/framebuffer route
- black and white test captures were compared
- official full-frame upload can complete far faster than the original Python replay
- Python replay was much slower due to conservative delays

However, the custom framebuffer route does not replace built-in numpad resources.

The public repository contains independently written analysis and replay scripts, but raw vendor captures and payload dumps remain local.

---

# 12. Firmware updater extraction completed

The official updater:

L99 ISP V1.23.exe

was identified as an Enigma Virtual Box container.

`evbunpack` v0.2.6 was installed locally in:

C:\temp\aula-l99-controller\.venv-evbunpack

The virtual filesystem was successfully extracted.

Relevant extracted files:

- Flash.ini
- HFD_Code_V2.2.bin
- HFD_Code_V2.3.bin
- HFD_ISP_TOOL_V1.31.exe
- Qt runtime DLLs and plugins

Observed approximate extracted sizes:

- Flash.ini: 0x623 bytes
- HFD_Code_V2.2.bin: 0x4AA88 bytes
- HFD_Code_V2.3.bin: 0x4C8A0 bytes
- HFD_ISP_TOOL_V1.31.exe: 0x18400 bytes

The expected name:

UartTFT-II_Flash.bin

was not present in the outer Enigma virtual filesystem.

Possible interpretations:

1. the file is inside a second-level container
2. the name is only a default path/string in HFD_ISP_TOOL_V1.31.exe
3. the full UI SPI-flash image is not distributed and must be read from the device
4. HFD_Code files may be controller code rather than the full UI resource image

All extracted vendor files remain excluded from GitHub.

No modified firmware has been flashed.

---

# 13. Third-party research reference

A highly relevant public project was found:

https://github.com/gavindi/Aula_L99_Linux

A local copy exists under:

C:\temp\aula-l99-controller\tools\Aula_L99_Linux-main

It is excluded from this repository and must not be vendored or committed.

This project reportedly already covers or documents:

- screen serial transport
- HID Feature Reports
- real-time telemetry fields
- photo-frame and background flash slots
- image conversion
- animated GIF container generation
- RGB565 palette handling
- RLE
- screen packet checksums
- audio spectrum data
- firmware-updater analysis
- LT7689-related work
- an unknown flash slot around 0x04200000

Use that project as the baseline reference and avoid repeating solved general-protocol work.

Our project’s additional findings include:

- full 17-key built-in numpad HID mapping
- verified built-in numpad touch behavior under Windows
- confirmation that normal framebuffer replay cannot overlay the built-in numpad page
- controlled CPU/GPU verification under Windows
- official monitor failure due to antivirus blocking
- extracted official updater components
- public cleaned Windows-focused tooling repository

Also used locally:

https://github.com/mos9527/evbunpack

Neither third-party tree is committed to this project.

---

# 14. What is completed

Completed and verified:

- project moved to C:\temp\aula-l99-controller
- clean public GitHub repository created and pushed
- MIT license added
- README added
- third-party references documented
- local/proprietary files excluded
- all public Python scripts compile
- invalid pseudo-Python Win32 file converted into documentation
- relevant USB devices identified
- numpad page mapped to 17 HID actions
- real-time 64-byte Feature Report identified
- date/time offsets identified
- CPU usage offset verified
- GPU usage offset verified
- GPU temperature offset verified
- AULA monitor fixed after antivirus blockage
- image/framebuffer upload route analyzed
- runtime numpad-overlay approach tested and disproved
- official updater’s Enigma VFS extracted
- HFD_Code V2.2 and V2.3 extracted
- HFD_ISP_TOOL_V1.31.exe extracted
- third-party Aula_L99_Linux project identified as a major reference
- local Git and remote histories merged correctly
- GitHub push succeeded
- local main branch is up to date with origin/main

---

# 15. What remains unresolved

Primary unresolved technical questions:

## Built-in page/resource system

- Where are the built-in page descriptors?
- Where are the built-in page bitmaps/icons?
- Are those resources located in HFD_Code_V2.3.bin, another MCU flash region, or external SPI flash?
- Where is the numpad page descriptor?
- Where is the home-widget routing table?
- Is the widget count fixed or table-driven?
- Can a new page descriptor be added?
- Is there an unused/hidden page ID?
- What is stored at the unknown flash slot around 0x04200000?

## Full UI flash extraction

- `UartTFT-II_Flash.bin` was not found in the updater’s outer VFS.
- Determine whether HFD_ISP_TOOL_V1.31.exe contains a nested resource/container.
- Determine whether the ISP protocol supports read-back.
- Establish a complete SPI-flash backup before any write.
- Establish a recovery or bootloader procedure before modifying flash.

## Numpad reskin

- Locate the numpad bitmap/icon resources.
- Locate touch/action descriptor table.
- Search for the 17 HID usage values as a firmware signature:
  53 54 55 56 5F 60 61 57 5C 5D 5E 59 5A 5B 58 62 63
- Determine whether those values appear contiguously, encoded, or generated.
- Trace neighboring structures to other page descriptors.
- Replace only one harmless visual resource first.
- Preserve original size/alignment/checksum.
- Do not flash until a verified backup exists.

## Add a new widget

- Determine whether a new home widget can be appended.
- Determine whether an existing hidden/unused widget can be activated.
- Determine whether page IDs and home routing are table-driven.
- Determine if the unknown flash slot can hold a custom page/resource set.
- Determine whether the real-time data-rendering engine can be reused for custom status icons.

## Animation

- Static reskin is likely easier than independent high-frame-rate animation.
- Multi-state or low-frequency dynamic icons may be possible.
- The 64-byte telemetry path proves low-cost local rendering exists, but it does not yet prove arbitrary numpad-icon updates.
- Audio-spectrum opcode/data may offer another dynamic-rendering path.
- Arbitrary per-icon animation is not yet verified.

---

# 16. Recommended next step

Do not do more generic screen-upload or CPU/GPU protocol tests.

The next task should be a read-only cross-analysis of:

C:\temp\aula-l99-controller\evbunpack_output\HFD_Code_V2.2.bin
C:\temp\aula-l99-controller\evbunpack_output\HFD_Code_V2.3.bin
C:\temp\aula-l99-controller\evbunpack_output\HFD_ISP_TOOL_V1.31.exe
C:\temp\aula-l99-controller\evbunpack_output\Flash.ini
C:\temp\aula-l99-controller\tools\Aula_L99_Linux-main\documentation\Firmware
C:\temp\aula-l99-controller\tools\Aula_L99_Linux-main\tools\aula_l99_screen

Priority:

1. inspect the third-party firmware documentation and code
2. search for 0x04200000 and all documented flash slots
3. inspect HFD_ISP_TOOL_V1.31.exe strings/imports/resources
4. test for nested containers without executing a flash operation
5. search both HFD_Code files for:
   - the 17 NumPad HID usage sequence
   - partial permutations of that sequence
   - screen dimensions 320 and 480 in little and big endian
   - known page/action constants
   - flash addresses from Aula_L99_Linux
6. compare V2.2 and V2.3 structurally
7. identify changed regions and embedded tables
8. write findings into project documentation
9. add a changelog entry for every verified step

Do not assume `HFD_Code_V2.3.bin` is the full UI image. Prove the role of each file first.

---

# 17. Change log

## 2026-11-07: Screen-transfer groundwork

Action:
- Captured and analyzed official image upload traffic.
- Compared solid-color transfers.
- Identified approximately 150 large data packets plus short commands.
- Investigated custom framebuffer encoding and CRC behavior.
- Built Python replay and extraction tools.

Files and artifacts:
- aula_official_refresh.pcapng
- aula_solid_black.pcapng
- aula_solid_white.pcapng
- aula_upload_test.pcapng
- replay_captured_screen.py
- push_solid_color.py
- decode_captured_frame.py
- extract_raw_usb_payloads.py
- CRC-analysis scripts

Result:
- Screen upload path could be replayed.
- Payload was confirmed not to be ordinary JPEG.
- Full-screen transfers were linked to the EEEF:268A serial screen controller.

Follow-up:
- Determine whether the same display path can affect built-in firmware pages.

## 2026-11-08: Numpad HID mapping

Action:
- Captured five numpad keys, then all numpad touch zones.
- Used tshark `usbhid.data`.
- Verified standard 8-byte keyboard HID reports.

Files:
- aula_numpad_5keys.pcapng
- aula_numpad_all_keys.pcapng
- docs/data/numpad_hid_mapping.csv

Result:
- 17 distinct numpad touch zones were mapped.
- Device 16, endpoint 0x81 produced the HID reports.

Conclusion:
- Built-in numpad page is a strong candidate for a Stream Deck reskin.
- Simple macro remapping alone is not the project goal.

Follow-up:
- Locate and alter visual resources while preserving action zones.

## 2026-11-08: Other built-in page captures

Action:
- Captured calculator, mouse/touchpad, home navigation, photo-frame touch behavior, and real-time page traffic.

Files:
- aula_calculator_all_keys.pcapng
- aula_mouse_controls.pcapng
- aula_home_all_buttons.pcapng
- aula_home_numpad_transition.pcapng
- aula_photo_touch_points.pcapng
- aula_realtime_idle_60s.pcapng

Result:
- Calculator did not emit normal keyboard HID reports.
- Touchpad page generated relative mouse traffic.
- Built-in page switching did not use full framebuffer uploads.
- Real-time page did not continuously transfer full frames.

Follow-up:
- Find lightweight real-time data transport.

## 2026-11-08: Batch capture analyzer

Action:
- Created `analyze_aula_captures.py`.
- Added endpoint, HID, consumer, mouse, touch, large-packet, and timing reports.
- Corrected tshark incompatibility.

Important correction:
- `frame_raw` is invalid in this tshark build under `-T fields`.
- Working payload sources are `usbhid.data`, `usbcom.data.out_payload`, and `usb.capdata`.

Result:
- Batch analysis completed across 16 captures.
- Numpad presses and large screen packets were detected correctly.

Follow-up:
- Keep the analyzer compatible with the current Wireshark build.

## 2026-11-08: USB device mapping

Action:
- Extracted enumeration VID/PID values.

Result:
- Device 15: EEEF:268A screen controller.
- Device 16: 0C45:800A keyboard HID.
- Device 13: 1A86:8091 touch/pointer controller.
- Device 6: 05E3:0626 USB hub and unrelated to telemetry.

Conclusion:
- Large amounts of device-6 traffic were excluded as hub/network noise.

## 2026-11-08: Real-time Feature Report protocol

Action:
- Isolated device-16 control traffic.
- Extracted 64-byte SET_REPORT payloads every approximately 5 seconds.
- Compared multiple cycles.

Result:
- Identified header `00 01 5A`.
- Identified date/time fields.
- Identified `AA 55` trailer.
- Confirmed a four-command cycle around the telemetry payload.

Follow-up:
- Map CPU/GPU and weather offsets.

## 2026-11-08: CPU-load verification

Action:
- Ran controlled baseline, CPU-load, and cooldown test.
- Captured real-time Feature Reports.

Result:
- Offset 13 tracked CPU usage.
- CPU usage rose to approximately 77 to 82 percent during load.
- Offset 14 remained zero on the test machine.

Conclusion:
- Offset 13 is verified CPU usage.
- CPU temperature was not provided by the official monitor on this hardware.

## 2026-11-08: Antivirus hardware-monitor issue

Action:
- Investigated telemetry values stuck at CPU 19 percent and GPU 27 percent.
- Found Bitdefender had blocked OpenHardwareMonitorServer.sys.
- Added a verified exception and restarted the monitor chain.

Result:
- OpenHardwareMonitorServer.exe ran and responded.
- Telemetry began changing.

Conclusion:
- Fixed values were caused by the PC-side sensor driver, not the USB protocol.

## 2026-11-08: GPU-load verification

Action:
- Logged `nvidia-smi`.
- Ran GPU-load capture.
- Compared AULA Feature Reports against NVIDIA usage and temperature.

Files:
- aula_realtime_gpu_load_v3.pcapng
- realtime_gpu_load_v3_payloads.txt
- nvidia_gpu_load_v3.csv
- gpu_load_test_v3_timeline.txt

Result:
- Offset 15 tracked GPU usage.
- Offset 16 tracked GPU temperature.
- Five-second AULA samples did not capture every one-second NVIDIA utilization spike, which is expected.

Conclusion:
- Offsets 15 and 16 are verified.

## 2026-11-08: Numpad framebuffer overlay test

Action:
- Entered numpad page with official AULA application closed.
- Started USB capture.
- Replayed a known working framebuffer upload through COM8.
- Pressed original numpad positions 7, 5, 1, +, Enter.

Result:
- Built-in numpad image did not change.
- All five HID actions remained functional.

Conclusion:
- Normal framebuffer/photo upload does not overlay built-in firmware pages.
- Runtime overlay approach is rejected.
- Resource or page-table modification is required.

## 2026-11-08: Official updater extraction

Action:
- Installed evbunpack locally.
- Listed the Enigma Virtual Box filesystem.
- Extracted the updater VFS without restoring the outer PE.

Files extracted locally:
- Flash.ini
- HFD_Code_V2.2.bin
- HFD_Code_V2.3.bin
- HFD_ISP_TOOL_V1.31.exe
- Qt dependencies

Result:
- Extraction completed successfully.
- `UartTFT-II_Flash.bin` was not present in the outer VFS.

Conclusion:
- Full built-in UI resources may be elsewhere or require device read-back.

Follow-up:
- Inspect the inner ISP tool and firmware files without writing to hardware.

## 2026-11-08: Aula_L99_Linux reference found

Action:
- Located https://github.com/gavindi/Aula_L99_Linux
- Downloaded a local copy.
- Marked the third-party tree as excluded from Git.

Result:
- Major portions of general protocol research already exist publicly.
- Project focus was narrowed to built-in page/resource/action modification.

Conclusion:
- Do not repeat solved photo/GIF/RTC/audio-spectrum work.
- Use the external project as a protocol baseline.

## 2026-11-08: Project relocation and GitHub cleanup

Action:
- Relocated project to:
  C:\temp\aula-l99-controller
- Added `.gitignore`.
- Excluded virtual environments, tools, captures, firmware, dumps, vendor assets, generated payloads, and third-party repositories.
- Created README, MIT license, requirements, documentation, and clean data mappings.
- Converted invalid Win32 pseudo-code into documentation.
- Compiled all remaining public Python files.

Result:
- Public GitHub repository created:
  https://github.com/miniz3210/aula-l99-controller
- Local and remote unrelated histories were merged.
- Push completed successfully.
- Local `main` tracks `origin/main`.
- Working tree was clean at completion.

Follow-up:
- Continue development using explicit `git add -- <file>` only.
- Maintain this changelog after every important step.

---

# 18. Required behavior for the next assistant

Start by acknowledging the verified state briefly, then inspect the requested current files before suggesting new reverse-engineering steps.

Do not ask me to rediscover device IDs, repeat CPU/GPU testing, repeat the numpad overlay test, or re-extract the outer Enigma container.

For every important action in the new chat:

1. state the exact goal
2. specify the input files
3. provide safe commands
4. state expected output
5. interpret actual output
6. update completed work
7. update remaining work
8. append a structured changelog entry

The immediate next analysis target is the built-in UI page/resource/action system, not general image upload.