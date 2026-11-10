# UI-Only Branch Verification — HFD_ISP_TOOL_V1.31.exe

**Method:** Offline static analysis only. No EXE executed. No hardware accessed. No USB/COM/HID opened.
**Binary:** `evbunpack_output\HFD_ISP_TOOL_V1.31.exe` (99,328 bytes, SHA-256 `3fd02273...`)
**Baseline:** Release v0.5.0, commit c82dc359782a3e833a0b81bb3d632496e4dc61df, working tree clean.
**Decision:** NO-GO (pre-existing).

## 1. Component inventory (local ignored artifacts)

| File | Size (bytes) | SHA-256 | Present in candidate package? |
|---|---:|---|---|
| `HFD_ISP_TOOL_V1.31.exe` | 99,328 | `3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282` | Yes |
| `UartTFT-II_Flash.bin` | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` | Yes |
| `Flash.ini` | 1,571 | `e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c` | Yes (optional) |
| `HFD_Code_V2.2.bin` | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` | **Absent** |
| `HFD_Code_V2.3.bin` (official) | 313,652 | `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03` | **Absent** |

## 2. String references recovered from the EXE

| File offset / VA | String | Section context |
|---|---|---|
| `0x0000CCDF` | `/UartTFT-II_Flash.bin` | string data |
| `0x0000CCCC` | `/HFD_Code_V2.2.bin` | string data |
| `0x0000CCB9` | `/HFD_Code_V2.3.bin` | string data |
| `0x0000CBB4` | `/Flash.ini` | string data |
| `0x0000CB9C` | `Mcu code, CRC = ` | string data |
| `0x0000CC2F` | `Flash code, FileCRC = ` | string data |
| `0x0000CC46` | `  FlashCRC = ` | string data |
| `0x0000CC65` | `Update flash is OK!!!!!!` | string data |
| `0x0000CC7E` | `Update flash is fail.....` | string data |
| `0x0000CC98` | `Read fail,please check the path!` | string data |
| `0x0000CA51` | `Time over!` | string data |
| `0x0000CB7A` | `Fail to Connect a mcu device` | string data |
| `0x0000CBC7` | `Fail to Connect a 268x device` | string data |
| `0x0000CB54` | `This file is over than mcu to update!` | string data |
| `0x0000CBE8` | `The file is over than the flash ic's size` | string data |

Source: `capture_analysis/hfd_isp_object_field_xrefs.txt` string extraction; `capture_analysis/hfd_isp_crc_dataflow.txt` and `capture_analysis/hfd_isp_crc_comparison.txt` disassembly ranges.

## 3. File-open calls traced (static)

| VA | Instruction sequence | Inferred call | Target file | Evidence |
|---|---|---|---|---|
| `0x004071D9` | `FF 15 10 96 41 00` `call dword ptr [0x419610]` | `fopen` | `UartTFT-II_Flash.bin` (inferred from size-read context) | `hfd_isp_object_field_xrefs.txt` MATCH 023 |
| `0x00407202` | `FF 15 14 95 41 00` `call dword ptr [0x419514]` | `fseek` | `UartTFT-II_Flash.bin` | `hfd_isp_object_field_xrefs.txt` MATCH 024; `cmp edi, 0x5c00` size bound |
| `0x00408E0D` / `0x00408FBE` | `FF 15 FC 95 41 00` `call dword ptr [0x4195fc]` | `fclose` | UI image handle | `hfd_isp_object_field_xrefs.txt` MATCH 061/047 |
| `0x00406076` | `FF 15 CC 96 41 00` `call dword ptr [0x4196cc]` | file/IO op | unspecified | `hfd_isp_object_field_xrefs.txt` MATCH 006/007 |

**No `fopen`/`fread`/`fseek` sequence targeting `HFD_Code_V2.2.bin` or `HFD_Code_V2.3.bin` was found in the recovered disassembly.** The only HFD_Code references are the three filename string constants (`0x0000CCCC`, `0x0000CCB9`, plus `/Flash.ini` at `0x0000CBB4`). No code path in `capture_analysis/hfd_isp_object_field_xrefs.txt` opens, reads, or sizes either HFD_Code file.

## 4. Branches after missing / open-failure HFD_Code files

**Not established.** No confirmed HFD_Code file-open path exists in the recovered static analysis, so there is no observable branch conditioned on HFD_Code open success/failure. The tool cannot be shown to refuse, skip, or default HFD_Code from this disassembly alone.

Confirmed branch points that *are* present:

| VA | Condition | Target on true | Target on false | Meaning |
|---|---|---|---|---|
| `0x00407BC9` | `cmp ebx, [esi+0x104]; je` | `0x407c7c` (success) | `0x00407BD5` `mov eax, 0xfffffffd` (fail) | FileCRC (`ebx`, `[object+0x100]`) vs FlashCRC (`[object+0x104]`) |
| `0x00407C63` | `cmp [esi+0xfc], 1; je` | `0x407bc9` | `0x00407C70` `cmp ebx,[esi+0x100]; jne 0x407bd5` | State flag `0xfc` gate |
| `0x00407C70` | `cmp ebx, [esi+0x100]; jne` | — | `0x00407bd5` return `0xfffffffd` | FileCRC vs `[object+0x100]` |
| `0x00407BA2` | `cmp [esi+0xc0], 1; je` | `0x407ad0` | fall through to size/logic | State flag `0xc0` gate |
| `0x004079DC` | `cmp [esi+0xfc], 1; je` | `0x407be2` (read FlashCRC from `[object+0x104]`) | fall through to read `[object+0x100]` | State flag selects CRC source |

Source: `capture_analysis/hfd_isp_crc_comparison.txt` (0x00407960–0x00407CB0) and `capture_analysis/hfd_isp_crc_dataflow.txt` (0x00408B80–0x004092C0).

## 5. HFD missing: skipped, defaulted, or fatal?

**Not established from static analysis.** No HFD_Code open/read path is present in the recovered xrefs, so neither a skip, a default, nor a fatal branch can be attributed to HFD_Code absence. The HFD_Code filename strings exist but are not referenced by any confirmed file-open instruction.

Limitation: The xref recovery covers 72 field accesses across 12,749 instructions; full control-flow recovery (all basic blocks, indirect calls, Qt slot dispatch) was not completed. A HFD_Code open path may exist outside the recovered matches.

## 6. UartTFT-II_Flash.bin independently opened and queued

**Yes — STRONG_INFERENCE.** `fopen` at `0x004071D9` (`call [0x419610]`) is immediately followed by `fseek` at `0x00407202` (`call [0x419514]`) and `cmp edi, 0x5c00` (23,552-byte size bound), then a read loop (`0x004072C3`–`0x00407667`) over `[ebx+0x110]` (buffer pointer at `object+0x110`). The image is queued into an object struct with fields:

| Object field | Offset | Meaning |
|---|---|---|
| `object+0x100` | FileCRC (host-computed CRC) | written at `0x00408BD5` |
| `object+0x104` | FlashCRC (device-reported CRC) | written at `0x00408C38` |
| `object+0xF4` | length | written at `0x00408BDB` |
| `object+0x110` | payload buffer pointer | written at `0x004071EF`, `0x00408B76` |
| `object+0xFC` | state flag (0/1) | set to 1 at `0x00409280`, cleared to 0 at `0x00408DB9` |
| `object+0xC0` | state flag | compared at `0x00407BA2`, `0x00407AD0` |
| `object+0xC8`, `object+0xC4` | state flags | compared at `0x00407B85`, `0x00407B8E` |

CRC algorithm: reflected IEEE polynomial, table at `0x0040f500`, init=0, xorout=0 (`123456789 → 0x2DFD2D88`). Verified in `capture_analysis/hfd_isp_crc_dataflow.txt` (0x00408BB0–0x00408BC8) and `capture_analysis/hfd_isp_crc_comparison.txt` (0x00407A1A–0x00407A39).

Source: `hfd_isp_object_field_xrefs.txt` MATCH 023–035; `hfd_isp_crc_dataflow.txt`; `hfd_isp_crc_comparison.txt`.

## 7. Erase/write order for UI versus HFD

**UNKNOWN.** No erase/write instruction sequence targeting either `UartTFT-II_Flash.bin` or an HFD_Code file is present in the recovered xrefs. The CRC comparison block (`0x00407BC9`) validates after transfer but no flash program/erase command is confirmed. HFD write order relative to UI cannot be determined.

Source: `capture_analysis/hfd_isp_object_field_xrefs.txt` (no flash program/erase opcodes matched); `hfd_isp_crc_verify_disassembly.txt` (0x00408C00–0x00409300, CRC only).

## 8. Conditions selecting V2.2 versus V2.3

**STRONG_INFERENCE only — not established from EXE code.** `Flash.ini` line 39 maps `0xEFAA21,2048,65536, W25N01GV`. The `6D 01 selector` query and flash-ID comparison against `0x00EFAA21` is documented in `docs/CONTROLLED_FLASH_PLAN.md` Section 4 (softce `protocol.md`) but the constant `0xEFAA21` does **not** appear as a string in `HFD_ISP_TOOL_V1.31.exe` (absent from the string extraction). No `cmp` against `0xEFAA21` or `0x00EFAA21` is present in the recovered xrefs.

So V2.2 vs V2.3 selection is inferred from `Flash.ini` + softce evidence, not from a confirmed branch instruction in this EXE.

## 9. Error strings and return paths for missing files

| String | VA | Context |
|---|---|---|
| `Read fail,please check the path!` | `0x0000CC98` | generic file-read failure; no confirmed HFD_Code-specific branch |
| `Update flash is fail.....` | `0x0000CC7E` | CRC mismatch path (0x00407BD5 returns `0xfffffffd`) |
| `Time over!` | `0x0000CA51` | timeout; no automatic retry path confirmed |
| Return codes | `0xfffffffd` (`0x00407BD5`), `0xfffffffe` (`0x00407BF0`), `0xffffffff` (`0x00407C55`) | fail paths |

No error string specifically names `HFD_Code_V2.2.bin` or `HFD_Code_V2.3.bin`. No branch returns an HFD_Code-specific error.

## 10. Whether UI write can finish without entering an HFD write path

**Yes — STRONG_INFERENCE.** The CRC verification block (`0x00407BC9` `je 0x407c7c`) completes for `UartTFT-II_Flash.bin` using only `object+0x100` (FileCRC) and `object+0x104` (FlashCRC). No HFD_Code field or open path participates. The success path returns 0 at `0x00407CA5`–`0x00407CAF` after the CRC match at `0x00407BCF`.

Limitation: Confirmed for the CRC/verify sub-path only. Whether the full update flow (erase, program, post-write) can complete without an HFD write path is not established because no erase/program instructions were recovered.

## 11. Classification

**STRONG_INFERENCE** (UI-only mode is plausible but not VERIFIED).

Evidence supporting UI-only:
- `UartTFT-II_Flash.bin` is independently opened (`fopen` `0x004071D9`), sized (`fseek` `0x00407202`), buffered (`object+0x110`), and CRC-verified (`0x00407BC9`) with no HFD_Code field involved.
- No `fopen`/`fread`/`fseek` path targets `HFD_Code_V2.2.bin` or `HFD_Code_V2.3.bin` in the recovered xrefs (72 field accesses).
- softce `recovery.md` confirms UI-only packages existed (`HFD_ISP_TOOL_V1.31.exe` + `UartTFT-II_Flash.bin`, no HFD_Code).

Limitations preventing VERIFIED_UI_ONLY:
- No explicit `if (HFD_Code missing) skip` or `if (HFD_Code open fail) default` branch is confirmed.
- Full control-flow graph not recovered (indirect calls, Qt dispatch, all basic blocks not mapped).
- No erase/program instructions found, so UI write completion cannot be fully proven independent of HFD.

## 12. Remaining blockers

1. Image-level self-checksum within `UartTFT-II_Flash.bin`: UNKNOWN (per-packet CRC verified; image-level self-checksum not located).
2. Exact UI-only package acceptance: STRONG_INFERENCE only; HFD_Code absence behavior not confirmed from EXE code.
3. HFD write order before/after UI: UNKNOWN (no erase/program path recovered).
4. V2.2 vs V2.3 selection branch: STRONG_INFERENCE only; `0xEFAA21` not found as an EXE string or cmp immediate.
5. Recovery behavior after interrupted write: UNKNOWN (`Time over!` string exists; no resume/rollback path confirmed).

## 13. GO / NO-GO

**Decision: NO-GO.** Pre-existing decision from handover. Not all critical blockers are VERIFIED: image-level self-checksum UNKNOWN, exact UI-only package construction STRONG_INFERENCE only, HFD write order UNKNOWN, interrupted-write recovery UNKNOWN.

## 14. Exact next task

Continue offline static analysis to (1) locate any image-level self-checksum field in `UartTFT-II_Flash.bin` beyond per-packet CRC; (2) recover the full control-flow graph around file-open to confirm whether HFD_Code files are ever opened; (3) determine erase/program instruction sequence for UI vs HFD write order. Do not execute any EXE or connect hardware.
