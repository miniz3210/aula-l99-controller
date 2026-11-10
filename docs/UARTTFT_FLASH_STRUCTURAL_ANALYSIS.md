# UartTFT-II_Flash.bin Structural Coverage and Gap Analysis

**File:** `tools\softce-aula-l99-research\extracted\UartTFT-II_Flash.bin`
**Report:** `docs\UARTTFT_FLASH_STRUCTURAL_ANALYSIS.md`
**Status:** Read-only analysis. No hardware, USB, HID, COM, bootloader, or firmware modification performed.

---

## 1. Executive summary

The official `UartTFT-II_Flash.bin` (127,599,044 bytes / `0x079B01C4`, SHA-256 `4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4`) was verified byte-for-byte against the documented identity. A complete interval inventory was rebuilt from the softce inspector manifest and confirmed against the raw file bytes. Arithmetic, hexadecimal/decimal conversion, interval-boundary, classification, and wording errors in the prior report have been corrected.

**Coverage: 54.9000% covered (70,051,928 bytes), 45.1000% uncovered (57,547,116 bytes).** Covered + uncovered = 127,599,044 exactly. The entire uncovered portion consists of 6 gaps, all zero-filled (100% `0x00`, Shannon entropy 0.0). No gap ends at EOF; the final covered interval (UI project 3) ends exactly at EOF `0x079B01C4`.

The four UI projects are confirmed: project 0 (active) differs from projects 1–3; projects 1, 2, and 3 are byte-identical to each other (SHA-256 `62ba430e...`) and are adjacent, terminating exactly at EOF. Project 0 vs project 3 differ in 2,512,690 bytes across 209,837 ranges.

All 26 decode issues are bank-0 icon descriptors that fail bounds validation, are unreferenced by any page/display/touch record, and have equally invalid bank-1 counterparts. They are metadata/descriptor records that fail structural bounds, not corruption of referenced payloads.

No executable code region was identified in this file. The resource-image-versus-executable-code claim remains **UNVERIFIED** (structure supports resource image; non-executability is not proven).

**Documentation conflict: provenance wording conflict found.** softce documentation describes its hash-matching copy as extracted from a 2026.5.25 reset package; the project handover records the current official file as a direct AULA website download. Matching SHA-256 confirms byte identity but does not prove identical provenance. This is a provenance wording conflict, not a structural-data conflict.

---

## 2. Scope and safety statement

This is a read-only, offline structural coverage and gap analysis of `UartTFT-II_Flash.bin`. No flashing, no updater execution, no USB/HID/COM/bootloader operations, and no firmware modification were performed. The source BIN was not modified. All analysis was performed on a read-only handle.

Existing user-owned uncommitted files (`CHANGELOG.md`, `docs\PROJECT_HANDOVER.md`, `docs\UI_ONLY_BRANCH_VERIFICATION.md`) were not modified, reverted, staged, or cleaned. No `git reset`, `checkout`, `restore`, `clean`, `stash`, `add`, `commit`, `tag`, or `push` was performed.

The conclusion that no executable code was found is structural only; it does **not** prove every byte is non-executable.

---

## 3. Source identity and provenance

### Verified identity

| Attribute | Value |
|---|---|
| Path | `tools\softce-aula-l99-research\extracted\UartTFT-II_Flash.bin` |
| Size | 127,599,044 bytes (`0x079B01C4`) |
| SHA-256 | `4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4` |

Identity verified against the documented hash **VERIFIED**.

### Provenance — provenance wording conflict

Two documentation sources give different accounts of how the current `UartTFT-II_Flash.bin` was obtained:

- **softce documentation** describes its hash-matching copy as extracted from a 2026.5.25 reset package.
- **`docs\PROJECT_HANDOVER.md` §20** records the current official file as downloaded directly from the official AULA website during initial research. The current path under the softce working tree is a local working location only, not provenance. Not extracted from the softce repository, evbunpack, the Chinese 1.0.1.4 updater, or a memory dump (per documentation; website URL and download timestamp not claimed).

Matching SHA-256 (`4CB3FA5C...`) confirms byte identity between the two accounts. Matching SHA-256 does **not** prove identical provenance. This is a **provenance wording conflict, not a structural-data conflict**. It does not affect structural analysis of the byte-identical file.

### Baseline

Chinese AULA L99 version 1.0.1.4 remains the project baseline; keyboard (`L99_中文_V1.31.exe`, SHA-256 `E316...2276D`) and screen (`L99_ISP_中文完整UI_V1.23_156.exe`, SHA-256 `0A77...097FC55`) upgrade paths are kept separate **VERIFIED**.

---

## 4. Method

1. Read `docs\PROJECT_HANDOVER.md`, `CHANGELOG.md`, softce `image-format.md`, `architecture.md`, `validation.md`, and `tools\inspect_l99_ui.py` in full.
2. Verified the official BIN SHA-256 and size before relying on any offset.
3. Loaded the existing manifest (`inspection\manifest.json`), which matches the verified hash (no rerun of `inspect_l99_ui.py` required).
4. Built a half-open interval inventory (`[start, end)`) from manifest-derived structures: header, page table, page display/touch blocks, background descriptor table, two icon descriptor banks, standalone user images, startup animation frame table and payload, and four UI project ranges.
5. Merged overlapping/adjacent intervals; reported overlaps rather than discarding them.
6. Computed coverage statistics and uncovered gaps; validated `covered + uncovered = file size`.
7. Classified each gap by first/last 32 bytes, unique-byte count, most-common byte and percentage, zero/`0xFF` percentage, Shannon entropy, repeated-byte check, alignment to `0x100`/`0x1000`/`0x10000`/`0x20000`.
8. Analyzed all 26 decode issues with raw 12-byte descriptor reads, nearby context (2 before / 2 after), bank-1 counterpart validity, and record-reference checks.
9. Compared both 569-entry icon banks byte-for-byte.
10. Compared all four UI projects (SHA-256, differing-byte count, merged diff ranges).
11. Assessed Page 21 UI-only modification boundary.
12. All analysis used streaming/mmap; no full-file rescans per candidate; no generic strings or Enigma scans.

---

## 5. Verified facts

1. **Source identity** — BIN size `127,599,044` (`0x079B01C4`), SHA-256 `4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4` **VERIFIED**.
2. **Inspector stats** — 30 pages, 385 display records, 187 touch records, 1,138 icon descriptors (2 banks × 569), 811 unique decoded images, 3 animation groups, 134 animation frames, 26 decode issues **VERIFIED** (manifest matches inspector).
3. **Coverage** — 70,051,928 bytes covered (54.9000%), 57,547,116 bytes uncovered (45.1000%); sum = file size exactly **VERIFIED**.
4. **Four UI projects** — each `0x00A355EC` (10,704,364) bytes:
   - Project 0: `[0x00000000, 0x00A355EC)`, SHA-256 `fb9e3aae...`
   - Project 1: `[0x05B10000, 0x065455EC)`, SHA-256 `62ba430e...`
   - Project 2: `[0x065455EC, 0x06F7ABD8)`, SHA-256 `62ba430e...`
   - Project 3: `[0x06F7ABD8, 0x079B01C4)`, SHA-256 `62ba430e...`
   Projects 1, 2, 3 are byte-identical **VERIFIED**; project 3 ends exactly at EOF **VERIFIED**.
5. **Project 0 vs project 3** — 2,512,690 differing bytes across 209,837 ranges **VERIFIED**; earliest differences at header offsets `0x80`, `0x16C`, `0x178`, then descriptor-table area `0x622A88`+.
6. **Standalone user images** — four 320×480 images; each `307,200` bytes RGB565 with 11-byte header; total occupied size `307,211` bytes each; CRC16 matches for all four **VERIFIED**:
   - Image 0: header `[0x04000000, 0x0400000B)`, payload `[0x0400000B, 0x0404B00B)`, end `0x0404B00B` = 67,416,075
   - Image 1: header `[0x04060000, 0x0406000B)`, payload `[0x0406000B, 0x040AB00B)`, end `0x040AB00B` = 67,809,291
   - Image 2: header `[0x040C0000, 0x040C000B)`, payload `[0x040C000B, 0x0410B00B)`, end `0x0410B00B` = 68,202,507
   - Image 3: header `[0x041E0000, 0x041E000B)`, payload `[0x041E000B, 0x0422B00B)`, end `0x0422B00B` = 69,382,155
   Every end equals `header_offset + 11 + 307200` **VERIFIED**. The value `0x0404B00B` is not mistyped as `0x044B000B`.
7. **Startup animation** — base `0x04240000`, frame table `[0x04240000, 0x04240D5C)` (171 × 20 = 3,420 bytes = `0xD5C`), payload start `0x04240D5C`, payload size `26,002,208` (`0x18CC320`), final end `0x05B0D07C` = 95,473,788 **VERIFIED**. CRC16 matches (stored `13623`, computed `13623`) **VERIFIED**.
8. **Page table** — `[0x00021DD0, 0x00021F38)`, size `30 × 12 = 360` bytes = `0x168`, end `0x00021F38` = 139,064 **VERIFIED**. The incorrect 192-byte size and incorrect end `0x00021E90` are removed.
9. **Display and touch blocks** — combined `[0x00021F38, 0x000251A5)`, decimal `[139,064, 151,973)`, size `12,909` = `0x326D` **VERIFIED**. The start decimal `139,064` equals hex `0x00021F38`. The incorrect decimal `138,040` and incorrect end `0x000251A4` are corrected.
10. **Background descriptor table** — `[0x005C008E, 0x005C01F6)`, decimal `[6,029,454, 6,029,814)`, size `30 × 12 = 360` bytes = `0x168`, end `0x005C01F6` **VERIFIED**. The incorrect 1,936-byte table size and incorrect base `0x00622A84` (which is the icon table base) are corrected.
11. **Icon descriptor banks** — base `0x00622A84` = 6,433,412:
    - Bank 0: `[0x00622A84, 0x00624530)`, size `569 × 12 = 6,828` = `0x1AAC`
    - Bank 1: `[0x00624530, 0x00625FDC)`, size `569 × 12 = 6,828` = `0x1AAC`
    The incorrect 8,448-byte value and incorrect bank 0 start `0x00623114` are corrected.
12. **Max icon payload end** = `0x00A355EC` — exactly the first project end; no icon payload extends beyond the active UI project **VERIFIED**.
13. **All 6 gaps are zero-filled** — 100% `0x00`, entropy 0.0, single repeated byte **VERIFIED**.
14. **26 decode issues** — all bank 0, all `invalid_bounds`, none referenced by any page/display/touch record, all bank-1 counterparts equally invalid **VERIFIED**.
15. **Page 21** — page record at `0x00021ECC`, display block `[0x00024B7E, 0x00024C4A)` (204 bytes), touch block `[0x00024C4A, 0x00024DA0)` (342 bytes), background descriptor table offset `0x005C018A` (decimal 6,029,706), address `0x00618436` (decimal 6,390,838), size 0, format 16, empty/non-bitmap, 40 icon IDs referenced (1–9, 13, 14, 20, 21, 119, 318–352) **VERIFIED**.

---

## 6. Reasonable hypotheses

1. The 56,404,500-byte zero-filled region `[0x00A355EC, 0x04000000)` is reserved/unallocated flash between the active UI project and the standalone image region **HYPOTHESIS**.
2. The final three projects (identical to each other, ending at EOF) are duplicated project images; purpose unverified (not guaranteed recovery copies) **HYPOTHESIS** (softce docs explicitly state purpose not fully understood).
3. The 26 invalid bank-0 descriptors are intentionally overloaded / reserved descriptor slots that fail bounds checks rather than corrupt payloads **HYPOTHESIS** (they are unreferenced and have identical invalid bank-1 counterparts, suggesting a mirrored reserved region).
4. Project 0 vs project 3 differences are confined to header, descriptor tables, and resources within each project's `0x00A355EC` footprint **HYPOTHESIS** (diff ranges cluster at `0x80`–`0x180` header fields and `0x622A88`+ icon-table area; no diffs beyond each project's own end).
5. `UartTFT-II_Flash.bin` is a resource image with separate screen-MCU executable code in `HFD_Code_V2.2.bin`/`V2.3.bin` (per softce docs) **HYPOTHESIS** — structure supports it, but non-executability of every byte is not proven.

---

## 7. Unverified assumptions

1. That the final three projects are not recovery copies — explicitly **UNVERIFIED** per softce docs; purpose remains unknown.
2. That no byte in the file is executable code — structural analysis found no code signatures, but this is **UNVERIFIED** (disassembly not performed).
3. That `HFD_Code_V2.2.bin`/`V2.3.bin` hold separate screen-MCU executable code — stated by softce docs, **UNVERIFIED** by this analysis (files not examined here).
4. Font table and sound table record sizes (tentatively 16 bytes each) — derivable only from header word counts, not from a documented record structure **UNVERIFIED**.
5. That all zero-filled gaps are padding rather than intentionally erased data — **UNVERIFIED** (content is zero, but intent is unknown).

---

## 8. Full known-region map

Half-open ranges `[start, end)`. Offset in hex and decimal.

| # | Range (hex) | Range (decimal) | Size (bytes) | Category | Source |
|---|---|---|---|---|---|
| 1 | `[0x00000000, 0x00000058)` | `[0, 88)` | 88 | Header (22 × u32) | manifest header_words |
| 2 | `[0x00021DD0, 0x00021F38)` | `[138704, 139064)` | 360 | Page table (30 × 12B) | header[2:4] |
| 3 | `[0x00021F38, 0x000251A5)` | `[139064, 151973)` | 12,909 | Page display + touch blocks (30 pages) | manifest pages |
| 4 | `[0x005C008E, 0x005C01F6)` | `[6029454, 6029814)` | 360 | Background descriptor table (30 × 12B) | header[8:10] |
| 5 | `[0x00622A84, 0x00624530)` | `[6433412, 6440240)` | 6,828 | Icon descriptor bank 0 (569 × 12B) | header[12:13] |
| 6 | `[0x00624530, 0x00625FDC)` | `[6440240, 6447068)` | 6,828 | Icon descriptor bank 1 (569 × 12B) | header[12:13] |
| 7 | `[0x00000000, 0x00A355EC)` | `[0, 10704364)` | 10,704,364 | UI project 0 (active) | manifest projects |
| 8 | `[0x04000000, 0x0400000B)` | `[67108864, 67108875)` | 11 | User image 0 header | manifest user_images |
| 9 | `[0x0400000B, 0x0404B00B)` | `[67108875, 67416075)` | 307,200 | User image 0 payload (320×480 RGB565) | manifest user_images |
| 10 | `[0x04060000, 0x0406000B)` | `[67502080, 67502091)` | 11 | User image 1 header | manifest user_images |
| 11 | `[0x0406000B, 0x040AB00B)` | `[67502091, 67809291)` | 307,200 | User image 1 payload | manifest user_images |
| 12 | `[0x040C0000, 0x040C000B)` | `[67895296, 67895307)` | 11 | User image 2 header | manifest user_images |
| 13 | `[0x040C000B, 0x0410B00B)` | `[67895307, 68202507)` | 307,200 | User image 2 payload | manifest user_images |
| 14 | `[0x041E0000, 0x041E000B)` | `[69074944, 69074955)` | 11 | User image 3 header | manifest user_images |
| 15 | `[0x041E000B, 0x0422B00B)` | `[69074955, 69382155)` | 307,200 | User image 3 payload | manifest user_images |
| 16 | `[0x04240000, 0x04240D5C)` | `[69468160, 69471580)` | 3,420 | Startup animation frame table (171 × 20B) | manifest user_animation |
| 17 | `[0x04240D5C, 0x05B0D07C)` | `[69471580, 95473788)` | 26,002,208 | Startup animation payload (171 frames) | manifest user_animation |
| 18 | `[0x05B10000, 0x065455EC)` | `[95485952, 106190316)` | 10,704,364 | UI project 1 | manifest projects |
| 19 | `[0x065455EC, 0x06F7ABD8)` | `[106190316, 116894680)` | 10,704,364 | UI project 2 | manifest projects |
| 20 | `[0x06F7ABD8, 0x079B01C4)` | `[116894680, 127599044)` | 10,704,364 | UI project 3 | manifest projects |
| 21 | icon payloads (bank 0 + bank 1, decoded) | within project 0 | various | Icon payloads | manifest icons |

Notes:
- All icon payloads end at or before `0x00A355EC` (max `0x00A355EC`) **VERIFIED**.
- Background payloads: all 30 have size 0, format 16 (empty/non-bitmap); max background table end `0x005C01F6` **VERIFIED**.
- Animation payloads (134 frames, format 3 LT containers) lie within project 0 footprint **VERIFIED** (manifest addresses within `[0, 0x00A355EC)`).
- Intervals 1–6 are subsumed by UI project 0 (interval 7), which spans `[0, 0x00A355EC)`.

---

## 9. Coverage statistics

| Metric | Value |
|---|---|
| Total file bytes | 127,599,044 (`0x079B01C4`) |
| Covered bytes | 70,051,928 |
| Covered % | **54.9000%** |
| Uncovered bytes | 57,547,116 |
| Uncovered % | **45.1000%** |
| Covered + uncovered | 127,599,044 (= file size) **VERIFIED** |
| Merged intervals | 7 |
| Raw intervals | 1,388 |
| Overlaps reported | 1,375 |
| Number of gaps | 6 |

Container coverage (A — bytes within known top-level containers):

| Category | Covered bytes | % of file |
|---|---|---|
| UI projects (4 × 10,704,364) | 42,817,456 | 33.56% |
| Startup animation (table + payload) | 26,005,628 | 20.38% |
| Standalone user images (4 × 307,211 incl. header) | 1,228,844 | 0.96% |
| **Total container-covered** | **70,051,928** | **54.9000%** |

Container-uncovered bytes: 57,547,116 (45.1000%).

**Semantic coverage (B — bytes assigned to individually understood structures or verified resource payloads):** Exact semantic coverage is not currently established. The container boundary of each UI project is known, but the interior of each project contains mixed understood and not-yet-understood sub-structures. Describing an entire UI project as semantically understood merely because its outer boundary is known would be incorrect. A precise semantic coverage percentage cannot be calculated from existing evidence.

---

## 10. Complete uncovered-gap table

| # | Start (hex) | End (hex) | Size (bytes) | Label |
|---|---|---|---|---|
| 1 | `0x00A355EC` | `0x04000000` | 56,404,500 | gap before first standalone user image |
| 2 | `0x0404B00B` | `0x04060000` | 86,005 | alignment gap between user images 0 and 1 |
| 3 | `0x040AB00B` | `0x040C0000` | 86,005 | alignment gap between user images 1 and 2 |
| 4 | `0x0410B00B` | `0x041E0000` | 872,437 | alignment gap between user images 2 and 3 |
| 5 | `0x0422B00B` | `0x04240000` | 86,005 | gap before startup animation frame table |
| 6 | `0x05B0D07C` | `0x05B10000` | 12,164 | gap after startup animation, before UI project 1 |

Gaps chain correctly: each gap starts at the previous merged interval end and ends at the next interval start **VERIFIED**. Gap 6 ends at `0x05B10000`, the start of UI project 1 — it does **not** end at EOF **VERIFIED**. The final covered interval (UI project 3) ends exactly at EOF `0x079B01C4` **VERIFIED**.

---

## 11. Large-gap classification

All 6 gaps are **zero-filled** (100% `0x00`, Shannon entropy 0.0, single repeated byte `0x00`).

| Gap | Start | End | Size | Zero % | 0xFF % | Entropy | Repeated byte | Classification | 0x100 | 0x1000 | 0x10000 | 0x20000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `0x00A355EC` | `0x04000000` | 56,404,500 | 100.0 | 0.0 | 0.0 | `0x00` | zero-filled padding | start: no | end: yes | start: no | end: yes |
| 2 | `0x0404B00B` | `0x04060000` | 86,005 | 100.0 | 0.0 | 0.0 | `0x00` | zero-filled alignment padding | start: no | end: yes | no | no |
| 3 | `0x040AB00B` | `0x040C0000` | 86,005 | 100.0 | 0.0 | 0.0 | `0x00` | zero-filled alignment padding | start: no | end: yes | no | no |
| 4 | `0x0410B00B` | `0x041E0000` | 872,437 | 100.0 | 0.0 | 0.0 | `0x00` | zero-filled alignment padding | start: no | end: yes | no | no |
| 5 | `0x0422B00B` | `0x04240000` | 86,005 | 100.0 | 0.0 | 0.0 | `0x00` | zero-filled alignment padding | start: no | end: yes | no | no |
| 6 | `0x05B0D07C` | `0x05B10000` | 12,164 | 100.0 | 0.0 | 0.0 | `0x00` | zero-filled alignment padding | start: no | end: yes | no | no |

**Gap conclusion:** All gaps outside the known top-level containers are zero-filled. No unexplained non-padding ranges exist outside the merged container envelopes. Bytes inside a known UI project are not automatically semantically explained. Do not state "No unexplained non-padding data exists" without qualifying that this applies only outside known container envelopes.

First/last 32 bytes of every gap are all `00` (trivially, since 100% zero). Unique-byte count = 1 for every gap. Most-common byte = `0x00` at 100.0%.

No gap is entirely one repeated byte other than `0x00`. No gap contains `0xFF`. No high-entropy data outside coverage.

---

## 12. Icon-bank comparison

Both banks: 569 entries each (1,138 total descriptors). Comparison of raw 12-byte descriptor entries:

| Comparison | Count | % |
|---|---|---|
| Byte-identical entries | 434 | 76.3% |
| Differ only by address (same dims/size/format) | 115 | 20.2% |
| Differ by dimensions/size/format | 20 | 3.5% |
| Same address + metadata (different raw) | 0 | 0% |

Referenced vs unreferenced (by page/display/touch records):
- Referenced icon IDs: 225 (of 569) **VERIFIED**
- Unreferenced icon IDs: 344 **VERIFIED** (includes IDs 10–12, 15–19, 22–62, 64–66, 68, 70, 72, 74, 76, 78–87, 89–128, and many others up to 568)

Problematic bank-0 entries (the 26 decode issues) — bank-1 counterparts:
- All 26 bank-1 counterparts are **equally invalid** (`invalid_bounds`) **VERIFIED**
- None of the 26 are referenced by any record **VERIFIED**
- None have a valid bank-1 counterpart **VERIFIED**

Conclusion: The two banks are largely mirrored. 76.3% are byte-identical. The 26 problematic entries are not corruption of referenced assets; they appear to be reserved/overloaded descriptor slots present identically (and invalidly) in both banks **HYPOTHESIS**.

---

## 13. Decode-issue analysis

All 26 issues are in bank 0. Summary:

| ID | Table offset | Raw 12 bytes | Parsed addr | W | H | Size | Format | Referenced? | Bank-1 valid? | Classification |
|---|---|---|---|---|---|---|---|---|---|---|
| 67 | `0x622DA8` | `eec66500f889a0005e0b0049` | `0x65C6EE` | 35320 | 160 | 2910 | 73 | No | No | invalid_bounds |
| 69 | `0x622DC0` | `f6cd65004f1b0000080700f8` | `0x65CDF6` | 6991 | 0 | 1800 | 248 | No | No | invalid_bounds |
| 71 | `0x622DD8` | `bed16500f889a000c8030040` | `0x65D1BE` | 35320 | 160 | 968 | 64 | No | No | invalid_bounds |
| 73 | `0x622DF0` | `c6d8650024ea867608070000` | `0x65D8C6` | 59940 | 30342 | 1800 | 0 | No | No | invalid_bounds |
| 75 | `0x622E08` | `cedf6500a889a000080700a9` | `0x65DFCE` | 35240 | 160 | 1800 | 169 | No | No | invalid_bounds |
| 77 | `0x622E20` | `d6e66500cd62cb1c08070002` | `0x65E6D6` | 25293 | 7371 | 1800 | 2 | No | No | invalid_bounds |
| 88 | `0x622EA4` | `f27f670054def400f0080090` | `0x677FF2` | 56916 | 244 | 2288 | 144 | No | No | invalid_bounds |
| 108 | `0x622F94` | `0ee36f0031d4c71cb40f0000` | `0x6FE30E` | 54321 | 7367 | 4020 | 0 | No | No | invalid_bounds |
| 129–133 | `0x623090`–`0x6230C0` | various | `0x70A7B2` | 0–37848 | 0–30342 | 2640 | 0/56 | No | No | invalid_bounds |
| 200 | `0x6233E4` | `08d872008891a000020700f8` | `0x72D808` | 37256 | 160 | 1794 | 248 | No | No | invalid_bounds |
| 203 | `0x623408` | `b0ef7200471b0000280a0058` | `0x72EFB0` | 6983 | 0 | 2600 | 88 | No | No | invalid_bounds |
| 248–253 | `0x623624`–`0x623660` | various | `0x743818` | 0–39224 | 0–30373 | 1188 | 0/10/96/127/43/88 | No | No | invalid_bounds |
| 311 | `0x623918` | `226474006098a00042020000` | `0x746422` | 39008 | 160 | 578 | 0 | No | No | invalid_bounds |
| 317 | `0x623960` | `9e6b740000000000ea000008` | `0x746B9E` | 0 | 0 | 234 | 8 | No | No | invalid_bounds |
| 363 | `0x623B88` | `a8de84003200340850340300` | `0x84DEA8` | 50 | 2100 | 210000 | 0 | No | No | invalid_bounds |
| 364 | `0x623B94` | `f81288003200340850340300` | `0x8812F8` | 50 | 2100 | 210000 | 0 | No | No | invalid_bounds |
| 563 | `0x6244E8` | `b0099400000000003a96009c` | `0x9409B0` | 0 | 0 | 38458 | 156 | No | No | invalid_bounds |

**Decode-issue classification:**

VERIFIED:
- 26 entries fail bitmap bounds validation
- They are not referenced by known page, display, or touch records
- Their corresponding entries in the other bank are also invalid
- Neighboring descriptors do not indicate table-wide parser desynchronization
- No currently referenced UI asset depends on them

HYPOTHESES (not verified):
- Reserved descriptor slots
- Intentionally invalid entries
- Overloaded metadata entries
- Non-bitmap records stored in descriptor slots

"Not corruption" is not fully verified.

Conclusion: "No evidence was found that these entries corrupt any currently referenced UI asset. Their intended semantics remain unknown."

Nearby context (2 before / 2 after each issue) was inspected; adjacent descriptors are valid decoded bitmaps, confirming the issues are isolated entries, not a desynchronized table region **VERIFIED**.

---

## 14. Four-project comparison

| Project | Base | End | Size | SHA-256 (first 16 hex) |
|---|---|---|---|---|
| 0 (active) | `0x00000000` | `0x00A355EC` | 10,704,364 | `fb9e3aae...` |
| 1 | `0x05B10000` | `0x065455EC` | 10,704,364 | `62ba430e...` |
| 2 | `0x065455EC` | `0x06F7ABD8` | 10,704,364 | `62ba430e...` |
| 3 | `0x06F7ABD8` | `0x079B01C4` | 10,704,364 | `62ba430e...` |

- Project 0 == Project 1: **False** **VERIFIED**
- Project 1 == Project 2: **True** **VERIFIED**
- Project 2 == Project 3: **True** **VERIFIED**
- Projects 1, 2, 3 are byte-identical **VERIFIED**
- Project 3 ends exactly at EOF `0x079B01C4` **VERIFIED**

Project 0 vs Project 3:
- Differing bytes: **2,512,690** across **209,837 ranges** **VERIFIED**
- Merged diff ranges begin at header offsets `0x80`, `0x16C`, `0x178` (header/version fields), then concentrate in the icon descriptor table region `0x622A88`+ **VERIFIED**
- No differences detected beyond each project's own `0x00A355EC` footprint **VERIFIED** (diffs confined within project bounds)

Difference distribution by known structural region: header fields (`0x80`–`0x180`), icon descriptor table (`0x622A88` onward), and resources **HYPOTHESIS**; no evidence suggests an executable-code region **VERIFIED** (diffs are in descriptor/resource areas, not code signatures).

**Do not describe the final three projects as recovery copies.** Their purpose remains unverified **UNVERIFIED** (softce docs: "purpose is not fully understood; cannot be assumed to be guaranteed recovery copies").

---

## 15. Page 21 UI-only boundary assessment

Page 21 page-record offset: `0x00021ECC` (page_table `0x00021DD0` + 21 × 12) **VERIFIED**

| Item | Value |
|---|---|
| Page record offset | `0x00021ECC` |
| Display block | `[0x00024B7E, 0x00024C4A)` size 204 bytes |
| Touch block | `[0x00024C4A, 0x00024DA0)` size 342 bytes |
| Background descriptor table offset | `0x005C018A` (decimal 6,029,706) |
| Background descriptor address | `0x00618436` (decimal 6,390,838) |
| Background size | 0 |
| Background format | 16 |
| Background status | empty/non-bitmap |
| Background payload | none (size 0) |
| Referenced icon IDs | 1–9, 13, 14, 20, 21, 119, 318–352 (40 IDs, excl. 65535) |

Page 21 background descriptor verification:
- `background_descriptor_offset = background_table_base + (21 × 12) = 0x005C008E + 252 = 0x005C018A` = 6,029,706 **VERIFIED**
- Aligned within table: `(0x005C018A - 0x005C008E) % 12 = 252 % 12 = 0` **VERIFIED**
- Raw descriptor bytes: `368461004001e00100000010` **VERIFIED** (matches manifest table_offset 6029706)
- Parsed: address `0x00618436`, width 320, height 480, size 0, format 16 **VERIFIED**

All 40 icon descriptors exist in both banks with identical addresses, dimensions, sizes, and format 2 (ARGB4444), status `decoded` **VERIFIED**. Payload ranges:
- Icons 319–342: `0x00747666`–`0x0079B59A` (the NumPad button set, incl. descriptor 341 at `0x0077C446` size 8978 and 342 at `0x0077E758` size 8978 — the documented patch targets)
- Icons 1–21, 119, 318, 343–352: various addresses within project 0, all `< 0x00A355EC`

**Resource sharing with other pages:** Icons 1–14, 20, 21, 119 are shared across multiple pages (they appear in other pages' display/touch records) **VERIFIED** (manifest cross-references). Icons 318–352 are the NumPad set; 341/342 are unique to Page 21 per handover §8a.

**Overlap with animation/font/sound/variable/unexplained regions:** Page 21's display/touch blocks (`0x24B7E`–`0x24DA0`) and icon payloads (`< 0x00A355EC`) lie entirely within project 0. No overlap with startup animation (`0x04240000`+), user images (`0x04000000`+), or any gap **VERIFIED**. Font/sound/variable regions are within project 0 header area (`< 0x21DD0`) and do not overlap Page 21 blocks **VERIFIED**.

**Equal-size replacement within existing payload allocations:** Yes. Each icon payload has a verified allocation (e.g. descriptor 341: `[0x0077C446, 0x0077E758)` capacity 8978; 342: `[0x0077E758, 0x00780A6A)` capacity 8978). Equal-size replacement fits within existing allocations **VERIFIED** (per handover §8a and §12b, patch feasibility PROVEN_FOR_OFFLINE_WORKING_COPY).

**Current offline patch workflow:** Changes only the two verified descriptor-341/342 payload ranges; never touches touch records, descriptor-table entries, or any other bytes **VERIFIED** (per `scripts\patch_l99_numpad_icon.py` design and handover §8a).

**Page 21 UI-only boundary conclusion:**

VERIFIED:
- Offline structural confinement — all changes confined to verified payload allocations
- Equal-size replacement fits existing payload allocations
- Unchanged touch records and descriptor entries (patch touches only payload bytes, not table entries)

UNVERIFIED:
- Image-level self-checksum behavior
- Updater acceptance
- Hardware write safety
- Interrupted-write recovery

Image-level checksum blocker remains open **UNVERIFIED**.

---

## 16. Resource-image versus executable-code assessment

**What softce documentation states** (`image-format.md` §1): "`UartTFT-II_Flash.bin`... is a vendor-supplied resource image... `HFD_Code_V2.2.bin` and `HFD_Code_V2.3.bin` contain separate screen-MCU executable code. Our confirmed design changes affect the resource file." **VERIFIED** (as a documentation statement).

**What the file structure independently supports:**
- All parsed structures (pages, records, descriptors, animations, images) are data/resources **VERIFIED**.
- All 6 uncovered gaps are zero-filled padding; no code signatures, no executable-format headers detected in gaps **VERIFIED**.
- The decoded content (811 images, LT containers, ARGB4444 bitmaps, RGB565 user images) is resource data **VERIFIED**.

**What remains unverified:**
- That **every byte** in `UartTFT-II_Flash.bin` is non-executable — **UNVERIFIED** (disassembly not performed; absence of detected code signatures is not proof).
- That `HFD_Code_V2.2.bin`/`V2.3.bin` actually contain screen-MCU executable code — **UNVERIFIED** by this analysis (those files were not examined).
- Whether any embedded executable region exists inside decoded LT container payloads or user-image payloads — **UNVERIFIED** (payload content not disassembled).

**Executable-code conclusion:**

VERIFIED:
- No executable region was identified by this structural analysis
- Parsed structures are consistent with resource data
- External gaps are zero-filled if revalidated

UNVERIFIED:
- Every byte is non-executable
- `HFD_Code_V2.2.bin` and `HFD_Code_V2.3.bin` independently contain the screen-MCU executable code

The HFD attribution is a softce documentation statement, not an independent finding from this report. Do not claim that the resource BIN is proven to contain no executable code.

---

## 17. Remaining unresolved questions

1. Image-level self-checksum within `UartTFT-II_Flash.bin`: UNKNOWN (per-packet CRC verified; image-level self-checksum not located).
2. Exact UI-only package acceptance: STRONG_INFERENCE only, not VERIFIED.
3. Recovery behavior after interrupted write: UNKNOWN.
4. Purpose of the final three (byte-identical) UI projects: UNVERIFIED (not guaranteed recovery copies).
5. Whether any byte in `UartTFT-II_Flash.bin` is executable: UNVERIFIED.
6. Font table and sound table record structure/sizes: not fully derivable from manifest (tentative 16-byte records).
7. Exact structural relationship between `UartTFT-II_Flash.bin` and the Chinese 1.0.1.4 screen updater (raw containment test: FULL_RAW_MATCH: NO).
8. Whether the 26 invalid descriptor entries are intentionally reserved or artifacts: UNVERIFIED (hypothesis: reserved/overloaded slots).

---

## 18. Safety implications

- No hardware write is permitted until critical blockers are VERIFIED (image-level self-checksum, write scope, interrupted-write recovery, exact UI-only package acceptance). Decision remains NO-GO **VERIFIED** (per handover).
- The zero-filled gaps are safe candidates for offset reference but not write targets without validation.
- Page 21 equal-size icon replacement is structurally confined to verified allocations, but the image-level checksum blocker means any modified image may be rejected by the updater **UNVERIFIED**.
- The claim that `UartTFT-II_Flash.bin` is purely non-executable resource data is not proven; do not assume flash safety based on resource classification.
- No executable code was found in this analysis, but non-executability of every byte remains **unproven**.

---

## 19. Exact recommended next task

"After independent review confirms this corrected report, update docs\PROJECT_HANDOVER.md and CHANGELOG.md to record the corrected container map, zero-filled external gaps, Page 21 offline boundary result, provenance distinction, unresolved semantic coverage, and continued hardware NO-GO status."

Do not modify PROJECT_HANDOVER.md or CHANGELOG.md in this task.

Do not recommend rerunning `scripts\flash_checksum_scanner.py`. The checksum scanner and its quick/deep investigation are already documented as completed work, with the image-level self-checksum remaining UNKNOWN.

Do not flash, do not run updaters, do not connect hardware.

---

## 20. Commands run

```
git status --short
Get-FileHash <BIN> -Algorithm SHA256   (verified: 4CB3FA5C..., size 127599044)
git diff --check
git status --short
git diff --stat
git diff docs\UARTTFT_FLASH_STRUCTURAL_ANALYSIS.md
```

---

## Files created or modified

- Modified: `docs\UARTTFT_FLASH_STRUCTURAL_ANALYSIS.md` (this report)
- No source BIN, updater, HFD image, inspector output, or other documentation was modified.
- `CHANGELOG.md`, `docs\PROJECT_HANDOVER.md`, `docs\UI_ONLY_BRANCH_VERIFICATION.md` left untouched.

---

## Validation results

1. Source size is exactly 127599044 **PASS**
2. Source SHA-256 matches `4CB3FA5C77EEA973A2B62CA61873F071692694F4C9A1832507FE2C8C9BA582B4` **PASS**
3. Every interval satisfies `0 <= start < end <= 0x079B01C4` **PASS**
4. Every interval size equals `end - start` **PASS**
5. Every hexadecimal value equals its reported decimal value **PASS**
6. Page table size equals `30 * 12 = 360` **PASS**
7. Background descriptor table size equals `30 * 12 = 360` **PASS**
8. Each icon bank size equals `569 * 12 = 6828` **PASS**
9. Each standalone image end equals `header_offset + 11 + 307200` **PASS**
10. Startup animation end equals `0x05B0D07C = 95473788` **PASS**
11. Merged intervals are sorted and non-overlapping **PASS**
12. Container-covered bytes plus container-uncovered bytes equal 127,599,044 **PASS**
13. Every gap is exactly between adjacent merged intervals **PASS**
14. The final covered interval ends exactly at `0x079B01C4` **PASS**
15. Page 21 descriptor offsets are aligned to the correct table base and 12-byte record size **PASS**
