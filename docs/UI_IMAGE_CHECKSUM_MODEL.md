# UI Image Checksum Model — AULA L99 `UartTFT-II_Flash.bin`

**File:** `UartTFT-II_Flash.bin`
**Size:** 127,599,044 bytes (0x079B01C4)
**SHA-256:** `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4`
**Source:** tools/softce-aula-l99-research/extracted/UartTFT-II_Flash.bin (verified hash)
**Method:** Offline static analysis only. No hardware, no EXE execution, no USB/COM/HID.

---

## 1. Checksum / integrity fields located in the image

| # | Location | Field | Width | Endian | Algorithm | Byte range covered | Verified by inspector? | Update required on resource replacement? |
|---|----------|-------|-------|--------|-----------|--------------------|------------------------|------------------------------------------|
| A | Four separate 320×480 user images at `0x04000000`, `0x04060000`, `0x040C0000`, `0x041E0000` | Stored CRC16 | 16-bit | LE | CRC16/MODBUS (reflected poly 0xA001, init 0xFFFF) | payload `[base+11, base+11+n)` where `n` = u32 size at `base` | YES — `inspect_l99_ui.py` `user_images`, `crc_matches` | N/A (these are full-screen images, not the patched button assets) |
| B | Animation frame records (171 frames, 20 bytes each) at `0x04240000` table | Stored CRC16 | 16-bit | LE | CRC16/MODBUS | GIF payload `[gif_start, gif_end)` | YES — `inspect_l99_ui.py` `user_animation`, `crc_matches` | N/A (animation, not the patched button assets) |
| C | 12-byte bitmap descriptors (icon banks + backgrounds) | payload_offset / width / height / size / format | 32/16/16/24/8 | LE | none (length field only) | descriptor entry itself | YES (bounds/parse) | NO for equal-size in-place (size field unchanged); YES if encoded size changes |
| D | Page records (`struct '<IHIH'`) | display_offset/display_length/touch_offset/touch_length | 32/16/32/16 | LE | none | page record | YES (parse) | NO |
| E | Widget / touch records | type / length_flags / payload | 16/8/var | LE | none | record | YES (parse) | NO (touch record `0x003B` unchanged) |
| F | Format-3 LT containers | internal_size, per-block content_length | 32 / 24 | LE | none (length fields only) | container | YES (decode assert) | NO (LT not used by descriptors 341/342; they are format 2) |
| G | Header word `0x174` | project size | 32 | LE | none | first UI project length | YES (assert `u32(0x174)==project_size`) | NO |
| H | Trailer (last ~0x400 bytes) | fill pattern `0x0FFF0FFF` | — | — | none | erased-flash fill | N/A | N/A |

**Fields with NO checksum:** page table, descriptor tables, resource headers (for format 0/1/2 raw bitmaps), format-3 LT containers, animation per-frame metadata except the payload CRC16 above, trailers. There is no per-resource checksum field on the format-2 ARGB4444 bitmap descriptors used by Page 21 buttons 341/342.

---

## 2. Image-level / global checksum

A stored image-level or whole-file checksum field was searched for in:
- the full 0x58-byte header (23 LE32 words),
- page-table, descriptor-table, and animation-table headers,
- the first and last 4 KiB of the file,
- all header words for values equal to file length (127,599,044 = 0x079B01C4) or payload length,
- repeated checksum tables / block-level metadata.

**No stored global checksum field was located.** The header contains offsets, counts, sizes, and a `0xFFFFFFFF` sentinel at `0x48`, but no candidate equals a CRC of any byte range, and no field holds the file length. The trailer is uniform erased-flash fill (`0x0FFF0FFF`), not a checksum.

**Image-level checksum status: NOT_FOUND** (no matching stored field located).
**Whether an image-level self-checksum exists at all: UNKNOWN** — lack of a located field is not proof of absence. Per project policy this remains a blocker until resolved.

---
## 5. Deep image-level self-checksum scan (`scripts/flash_checksum_scanner.py`)

A structured offline scanner (`scripts/flash_checksum_scanner.py`) re-tests the image-level self-checksum question over fixed-structure regions only. It supports `--mode quick` (targeted structural checks, under 30 seconds) and `--mode deep` (full investigation, cached by factory hash, patched hash, scanner version, scanner source hash, algorithm list, and region-map hash). Results are cached so identical inputs return immediately.

### Regions scanned

| Region | Start | End | Length | Result |
|--------|-------|-----|--------|--------|
| main_header | 0x00000000 | 0x00000058 | 88 | NO_MATCH |
| page_table | 0x00021DD0 | 0x00021F38 | 360 | NO_MATCH |
| startup_animation | 0x04240000 | 0x05B0D07C | 26,005,628 | NO_MATCH |
| first_64kiB | 0x00000000 | 0x00010000 | 65,536 | NO_MATCH |
| last_64kiB | 0x079A01C4 | 0x079B01C4 | 65,536 | NO_MATCH |
| header_words_vs_whole_image | 0x00000000 | 0x0000005C | 92 | NO_MATCH |

Regions skipped (bounds not fixed in `image-format.md`): widget_records_start, font_table, sound_table, animation_table, background_descriptors, descriptor_bank0, descriptor_bank1, all four display images, UI projects 2-4.

### Algorithms tested (per region)
- CRC16/MODBUS (reflected poly 0xA001, init 0xFFFF, xorout 0)
- CRC32 reflected IEEE (init=0, xorout=0)
- Standard CRC-32 (non-reflected, init 0xFFFFFFFF, xorout 0xFFFFFFFF)
- Additive sum 16-bit
- Additive sum 32-bit

### Match convention
A match requires the computed checksum (over the region with the candidate field zeroed) to equal a stored u16/u32 LE value at a specific plausible field offset (first or last u16/u32 of the region, or any header word). Birthday-paradox "value appears anywhere in the range" matches are NOT reported, since a 16-bit value over a 64 KiB region is statistically likely to appear somewhere by chance.

### Result
No stored field at any plausible offset matches any tested algorithm over any fixed-structure region.
**Image-level self-checksum status: UNKNOWN** (per project policy, lack of a match is not proof of absence).

---

## 3. Distinction of CRC concepts

| Concept | Where it lives | Algorithm | Stored in `UartTFT-II_Flash.bin`? | Notes |
|---|---|---|---|---|
| Checksums stored inside the BIN | Per-resource: 4 user images (CRC16 at `base+9`), animation frames (CRC16 per 20-byte record) | CRC16/MODBUS reflected | YES (fields A, B above) | Only for those specific resource types; format-2 button bitmaps have none |
| Packet CRC used during transfer | ISP tool memory / wire (`4A 30` frames) | CRC32 reflected IEEE, init=0, xorout=0 | NO | Computed per packet over `offset:LE32 \| payload_length:LE16 \| payload`, appended LE32. `123456789 → 0x2DFD2D88`. Verified in `HFD_ISP_TOOL_V1.31.exe` disassembly (table at `0x40f500`) |
| Host-computed whole-file CRC | ISP tool object field `[object+0x100]` (FileCRC) at runtime | CRC32 over transferred file | NO | Not a stored BIN field; populated at runtime from the transferred bytes |
| Device-reported flash CRC | ISP tool object field `[object+0x104]` (FlashCRC) at runtime | read from device | NO | Compared against host FileCRC at disassembly `0x407BC9` / `0x407C70` |
| Per-resource CRC16 | 4 user images + animation frames | CRC16/MODBUS | YES (fields A, B) | Verified `crc_matches` in inspector |

---

## 4. Implications for replacing Page 21 button images (descriptors 341/342)

- Descriptors 341 (unpressed) and 342 (pressed) are **format 2 = ARGB4444 raw 16-bit packed**.
- The 12-byte descriptor entry stores only `address, width, height, size(low24), format(high8)` — **no checksum field**.
- Equal-size in-place replacement (8978 bytes each) changes **no checksum field anywhere** in the image; no descriptor-table, page-table, or global field needs updating.
- No per-resource CRC16 covers these assets, so no per-resource checksum must be recomputed.
- The only image-level integrity that could matter is the **unresolved** global/self-checksum (status UNKNOWN, see above) — this is a blocker, not something the patcher currently updates.
