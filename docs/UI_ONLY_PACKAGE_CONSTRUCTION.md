# UI-Only Package Construction — AULA L99 Screen ISP

**Method:** Offline static analysis only. No EXE executed. No hardware accessed. No USB/COM/HID opened. All identity verified by size and SHA-256.

---

## 1. Component inventory — every located copy, size, SHA-256

| File | Location | Size (bytes) | SHA-256 | Status |
|---|---|---:|---|---|
| `HFD_ISP_TOOL_V1.31.exe` | `evbunpack_output/HFD_ISP_TOOL_V1.31.exe` | 99,328 | `3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282` | Verified (matches reference) |
| `L99 ISP V1.23.exe` | `evbunpack_output/` (inner PE after EVB unpack) | 111,008 | `e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0` | Verified |
| `Flash.ini` | `evbunpack_output/Flash.ini` | 1,571 | `e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c` | Verified |
| `UartTFT-II_Flash.bin` | `tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin` | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` | Factory reference, verified |
| `HFD_Code_V2.2.bin` | `evbunpack_output/HFD_Code_V2.2.bin` | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` | Verified |
| `HFD_Code_V2.3.bin` (earlier build) | `evbunpack_output/HFD_Code_V2.3.bin` | 313,504 | `b277823234fcab7137963896493bcb6896fd985fc972354166fcfc584534e37f` | Same name, DIFFERENT hash from official |
| `HFD_Code_V2.3.bin` (official) | `tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin` | 313,652 | `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03` | Official reference, verified |
| Screen Reset EXE | within official Reset ZIP (not extracted/tracked) | 194,946,048 | `8d52849afefeadf3a5d28a5e226f2c7a372a9376e1286f35c286d9b820d1ae84` | Local/ignored, not executed |
| Official Reset ZIP | `tools/softce-aula-l99-research/input/L99-reset.zip` | 45,080,624 | `e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3` | Local/ignored |

**Same-name warning confirmed:** `evbunpack_output/HFD_Code_V2.3.bin` (313,504 bytes, `b2778232...`) differs from `tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin` (313,652 bytes, `a76806ad...`). Identical filenames must be identified by hash, never by name.

---

## 2. Static analysis of `HFD_ISP_TOOL_V1.31.exe` (not executed)

Recovered via EVB unpack; 99,328 bytes. Read-only disassembly-level inspection of `capture_analysis/hfd_isp_crc_*.txt`, `hfd_isp_object_field_xrefs.txt`, and `local_analysis/pe_reports/HFD_ISP_TOOL_V1.31.exe.json`.

### File-open / CWD assumptions
- Direct string references to `/UartTFT-II_Flash.bin`, `/HFD_Code_V2.2.bin`, `/HFD_Code_V2.3.bin`, `/Flash.ini` (root-relative, alongside the tool).
- No absolute install path identified; tool expects the named files in its working directory / package folder.

### Selection logic for `UartTFT-II_Flash.bin`
- Exact filename match required (`/UartTFT-II_Flash.bin` string ref).
- Size check: 127,599,044 bytes verified; enforcement inferred from error strings ("This file is over than mcu to update!", "The file is over than the flash ic's size").

### Behavior when HFD_Code files are absent
- Both ISP tools contain string refs to all three files (`UartTFT-II_Flash.bin`, `HFD_Code_V2.2.bin`, `HFD_Code_V2.3.bin`, `Flash.ini`).
- Whether absence of HFD_Code files causes refusal or is tolerated is **not established** by static analysis (no code path fully confirmed).

### UI-only versus combined-update branches
- softce `recovery.md` confirms: "Separate UI packages used `HFD_ISP_TOOL_V1.31.exe` with a resource image named `UartTFT-II_Flash.bin`, without HFD_Code or keyboard MCU files. The updater still transfers the entire resource image." → UI-only packages are confirmed to exist.
- Both tools statically reference all three files, so a combined UI+HFD write is possible; actual write scope per tool is **not established** by static analysis alone.

### File-size checks
- Image size 127,599,044 bytes verified; error strings indicate size enforcement (STRONG_INFERENCE).

### Update order
- Not determined from static analysis (no confirmed HFD-before-UI or UI-before-HFD ordering).

### Address and length construction
- ISP packet: `4A 30 | offset:LE32 | payload_length:LE16 | payload | CRC32:LE32` (protocol.md).
- Full 127,599,044-byte image transferred (verified per softce; C13 VERIFIED).
- Address/length are per-packet LE32/LE16; full-image range implied.

### CRC calculation and comparison
- Per-packet CRC32: reflected IEEE polynomial, init=0, xorout=0, over `offset \| length \| payload`. `123456789 → 0x2DFD2D88`. Table at `0x40f500`.
- Host FileCRC stored at `[object+0x100]`; device FlashCRC at `[object+0x104]`; compared at `0x407BC9` / `0x407C70`.
- Status strings: "Update flash is OK!!!!!!" / "Update flash is fail....." / "Read fail,please check the path!" / "Time over!".

### Success and failure paths
- OK path reached when host FileCRC == device FlashCRC (branch at `0x407BC9` je `0x407c7c`).
- Fail path returns error codes `0xfffffffd`, `0xfffffffe`, `0xffffffff`.

---

## 3. Does a UI-only package consist exactly of `HFD_ISP_TOOL_V1.31.exe` + `UartTFT-II_Flash.bin` (+ optionally `Flash.ini`), no HFD_Code?

**Confirmed existence:** UI-only packages are confirmed to exist per softce (updater used with `UartTFT-II_Flash.bin`, without HFD_Code or keyboard MCU files).

**Exact construction VERIFIED? NO.** Static analysis shows the EXE references all three files; whether the updater refuses, skips, or uses an embedded default when HFD_Code files are absent is not established. The exact directory layout (which files must be present, whether `Flash.ini` is mandatory, relative paths) is not verified beyond filename/path exactness.

So: UI-only package **consists of** `HFD_ISP_TOOL_V1.31.exe` + `UartTFT-II_Flash.bin`, optionally `Flash.ini`, and no HFD_Code files **per softce evidence**, but this is **STRONG_INFERENCE**, not VERIFIED, for the exact accepted construction.

---

## 4. Updater behavior questions (static only)

| Question | Answer | Confidence |
|---|---|---|
| Transfers only files that exist? | Not established (references all three; whether it skips missing HFD_Code unknown) | UNKNOWN |
| Requires all three filenames? | Not established | UNKNOWN |
| Selects mode based on device/firmware version? | `6D 01 selector` query; flash ID compared against `0x00EFAA21` selects HFD V2.2/V2.3 | STRONG_INFERENCE |
| Writes HFD code before or after UI resources? | Not determined | UNKNOWN |
| Uses embedded default if a file is missing? | Not established | UNKNOWN |
| Refuses to start if HFD files absent? | Not established | UNKNOWN |

---

## 5. Repository evidence for exact package directory layout

`docs/FIRMWARE_PACKAGE_MAP.md` and `docs/PROJECT_HANDOVER.md` map component relationships but do not reverse-engineer the EVB container or document an exact UI-only package directory tree. softce `recovery.md` confirms UI-only packages existed but gives no file-by-file layout recipe.

Per the project rule: a statement that UI-only packages existed is **not** elevated into a verified construction recipe unless filenames, layout, and updater behavior are all supported. They are not all supported here.

---

## 6. Precise package tree per mode (classification)

### UI-only
```
<package root>/
  HFD_ISP_TOOL_V1.31.exe      (99,328 bytes, 3fd02273...)
  UartTFT-II_Flash.bin        (127,599,044 bytes, 4cb3fa5c...)
  Flash.ini                   (optional; 1,571 bytes, e515905c...)
```
**Confidence:** STRONG_INFERENCE — existence confirmed; exact accepted construction not verified.

### HFD-only (if present)
Not present as a separately documented mode in this repository. HFD_Code_V2.2/V2.3 are bundled with the screen reset package; no verified HFD-only package tree exists.
**Confidence:** UNKNOWN.

### Combined reset
```
<package root>/
  HFD_ISP_TOOL_V1.31.exe      (or L99 ISP V1.23.exe)
  UartTFT-II_Flash.bin
  HFD_Code_V2.2.bin
  HFD_Code_V2.3.bin
  Flash.ini
```
**Confidence:** STRONG_INFERENCE — both ISP tools reference all three files; combined write possible; exact scope not established.

---

## 7. Confidence summary

| Finding | Confidence |
|---|---|
| UI-only packages existed (softce) | STRONG_INFERENCE |
| Exact UI-only package construction verified | NOT_VERIFIED (UNKNOWN) |
| HFD_ISP_TOOL_V1.31.exe + UartTFT-II_Flash.bin (+ optionally Flash.ini), no HFD_Code | STRONG_INFERENCE |
| Exact filename/path `UartTFT-II_Flash.bin` required | VERIFIED |
| Image size 127,599,044 enforced | STRONG_INFERENCE |
| Per-packet CRC32 reflected IEEE | VERIFIED |
| Full image transferred (not ranges) | VERIFIED |
| HFD V2.2/V2.3 via flash ID `0xEFAA21` | STRONG_INFERENCE |
| HFD files required vs optional / embedded default | UNKNOWN |
| Write scope UI-only vs combined HFD | STRONG_INFERENCE (not VERIFIED) |
