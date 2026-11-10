# Page 21 First Patch Plan — AULA L99 `UartTFT-II_Flash.bin`

**Status:** Offline static-analysis plan only. No firmware created or patched in this task. No hardware, no EXE execution, no USB/COM/HID.

**Target image:** `UartTFT-II_Flash.bin` — size 127,599,044 bytes (0x079B01C4), SHA-256 `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` (verified factory reference).

**Target button:** Page 21 return code `0x003B` (NumPad 1), unpressed descriptor `341` / `0x0155`, pressed descriptor `342` / `0x0156`.

---

## 1. Descriptor-table offsets

Icon descriptor table base: `0x00622A84` (header word at `0x30`), icon count 569 (header word at `0x34`), two banks of 569 × 12-byte entries.

| Descriptor | ID (hex) | Bank | Exact descriptor entry file offset | Raw descriptor bytes | Descriptor entry length |
|---|---|---|---|---|---|
| 341 (unpressed) | 0x0155 | 0 | `0x00623A80` (6,437,504) | `46c477004300430012230002` | 12 |
| 342 (pressed) | 0x0156 | 0 | `0x00623A8C` (6,437,516) | `58e777004300430012230002` | 12 |

Computation: `icon_table + (bank * icon_count + descriptor_id) * 12`
- 341: `0x00622A84 + (0*569 + 341)*12 = 0x00622A84 + 0xFFC = 0x00623A80` ✓
- 342: `0x00622A84 + (0*569 + 342)*12 = 0x00622A84 + 0x1008 = 0x00623A8C` ✓

Descriptor entry layout (LE): `u32 payload_offset, u16 width, u16 height, u32 packed` where low 24 bits = encoded size, high 8 bits = format.

---

## 2. Asset addresses, formats, dimensions, stored lengths

| Descriptor | Source asset logical address / file offset | Format | Format name | Width | Height | Encoded payload length | Full encoded record length | Encoded range (inclusive) |
|---|---|---|---|---|---|---|---|---|
| 341 | `0x0077C446` (7,849,030) — direct file offset, no translation | 2 | ARGB4444 (raw 16-bit packed) | 67 | 67 | 8,978 | 12 (entry only; payload separate) | `0x0077C446 .. 0x0077E757` |
| 342 | `0x0077E758` (7,858,008) — direct file offset, no translation | 2 | ARGB4444 (raw 16-bit packed) | 67 | 67 | 8,978 | 12 (entry only; payload separate) | `0x0077E758 .. 0x00780A69` |

Address translation: **direct file offset** — manifest address == file offset in `UartTFT-II_Flash.bin`; no bank/segment translation.

Encoded record layout (format 2): raw ARGB4444 LE u16 pixels, `width * height * 2 = 67*67*2 = 8,978` bytes. No per-resource checksum header/trailer on these format-2 bitmaps.

---

## 3. Allocation limits

| Descriptor | Allocation start | Allocation end (exclusive) | Allocation capacity | Next confirmed asset boundary | Boundary verified? | Overlap with adjacent asset? |
|---|---|---|---|---|---|---|
| 341 | `0x0077C446` | `0x0077E758` | 8,978 | `0x0077E758` (== descriptor 342 address) | YES | No |
| 342 | `0x0077E758` | `0x00780A6A` | 8,978 | `0x00780A6A` (next descriptor address) | YES | No |

Replacement-size limit = allocation capacity **8,978 bytes** per descriptor.

---

## 4. Per-resource checksum fields

Descriptors 341/342 are **format 2 (ARGB4444 raw)**. The descriptor entry stores only `address, width, height, size(low24), format(high8)` — **no checksum field**. There is **no per-resource CRC16** covering format-2 button bitmaps (CRC16/MODBUS exists only for the four separate 320×480 user images and the animation frames, per `docs/UI_IMAGE_CHECKSUM_MODEL.md`).

**Per-resource checksum fields requiring update on replacement: none.**

---

## 5. All references to each asset

Both descriptors are referenced by exactly **one** touch record, on **Page 21**, return code `0x003B`, goto_page `65535`.

| Descriptor | Role | Referencing record | Page | Offset | Return value | Goto page | Rectangle | Shared elsewhere? |
|---|---|---|---|---|---|---|---|---|
| 341 | unpressed | Page 21 touch record | 21 | `0x00024A81` (150,697) | `0x003B` | 65535 | [13,337,79,403] | No (1 reference) |
| 342 | pressed | Page 21 touch record | 21 | `0x00024A81` (150,697) | `0x003B` | 65535 | [13,337,79,403] | No (1 reference) |

Touch record layout: `u16 type_flags, u8 length_flags, payload(16)` with payload `x1,y1,x2,y2,return_value,unpressed_icon,pressed_icon,goto_page` (8 × LE16).

The touch record `0x003B` itself is **unchanged** by this patch; only the icon payload bytes at the two descriptor addresses change.

---

## 6. Equal-size in-place replacement — structurally sufficient?

**Yes, for equal-size (8,978-byte) in-place replacement:**

- Replacement writes exactly within the verified allocation `[start, start+8978)` for each descriptor.
- Boundary verified: next descriptor address == allocation end (no overlap, no gap adjustment).
- No descriptor-table fields change (address, width, height, size, format all unchanged).
- No page-table, touch-record, or global metadata changes.
- No per-resource checksum exists for format-2 bitmaps, so no checksum field needs recomputing.
- Source image bytes outside the two ranges are preserved byte-for-byte.

**Structurally sufficient: YES** — equal-size in-place replacement avoids relocation and requires no metadata or checksum updates **within the verified format**.

**Caveat (blocker):** An unresolved **image-level self-checksum** may exist (status `NOT_FOUND` for a stored field; existence `UNKNOWN`). If the updater or screen MCU validates an image-level checksum that is not updated, the patched image could be rejected. This is outside the per-resource/descriptor scope and remains blocker #1.

---

## 7. Shorter replacement with padding

**Valid:** A shorter encoded asset padded to exactly 8,978 bytes within the same allocation is structurally valid, provided:
- The padded bytes preserve the allocation bounds (write exactly 8,978 bytes).
- The format (2) and dimensions (67×67) remain unchanged so the decoder interprets the same pixel count.
- Padding content must be decodable by the MCU (e.g., transparent/zero ARGB4444) to avoid visual artifacts; validity of padding *content* is a runtime concern not established statically.

A replacement **longer** than 8,978 bytes is **not valid** in place (would overflow into the adjacent asset at `0x0077E758`/`0x00780A6A`); it would require relocation and descriptor-table updates.

---

## 8. Page or global metadata that must change

| Metadata | Must change? | Reason |
|---|---|---|
| Descriptor entry (address/width/height/size/format) | NO (equal-size) | All fields unchanged |
| Page table entry (display/touch offsets/lengths) | NO | Page record untouched |
| Touch record `0x003B` (return/goto/rect/icons) | NO | Only icon *payload* changes, not the record's icon IDs |
| Global header | NO | No image-level checksum field located to update |
| Per-resource CRC16 | N/A | None exists for format-2 bitmaps |

**No page or global metadata must change** for equal-size in-place replacement.

---

## 9. Verification outputs to produce (future task)

When the patch is executed, generate:
- `patch_report.json` (source/target SHA-256, sizes, ranges, round-trip flags)
- `diff_ranges.json` (before/after SHA-256 per range)
- `normal_encoded.bin`, `pressed_encoded.bin` (exactly 8,978 bytes each)
- `normal_roundtrip.png`, `pressed_roundtrip.png`
- Confirm patched size == 127,599,044 and only the two ranges differ from factory.
