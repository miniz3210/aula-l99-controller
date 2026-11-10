# Vendor Firmware Provenance — AULA L99 Screen Resource Image

**Method:** Offline static analysis only. No hardware accessed. No EXE executed. No ZIP, EXE, BIN, or extracted asset added to Git. Vendor binaries are local only and ignored by Git; they are NOT redistributed in the public repository.

---

## 1. Official package record

| Field | Value |
|---|---|
| Official listing URL | https://www.aulastar.com/search.html?typeid=28&method=1&channelid=4&type=sonself&keywords=L99 |
| Direct ZIP URL | https://www.aulastar.com/uploads/soft/20240621/L99%20reset%20firmware%202026.5.25.zip |
| Filename | L99 reset firmware 2026.5.25.zip |
| Size | 45,080,624 bytes |
| SHA-256 | e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3 |
| Discovery reference | softce/aula-l99-research docs/recovery.md |
| Release date (package label) | 2026-05-25 |

### URL directory date is not the release date

The ZIP URL path contains directory `20240621`. That directory date is **not** the release date. The package label and official contents date the release as `2026-05-25`. The `20240621` path segment reflects the server upload/folder date, not the firmware release date.

---

## 2. Contents identified from the ZIP (verified hashes, local only)

| File | Size (bytes) | SHA-256 | Status |
|---|---:|---|---|
| Reset ZIP | 45,080,624 | `e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3` | Local/ignored |
| Screen reset EXE | 194,946,048 | `8d52849afefeadf3a5d28a5e226f2c7a372a9376e1286f35c286d9b820d1ae84` | Local/ignored |
| Keyboard reset EXE | 2,213,280 | `0a946a5d41a872f32e3f3cbdd0d73f9dd7058ea17d3f2a89b2b1bf5c3ed6b217` | Local/ignored |
| HFD_Code_V2.2.bin | 305,800 | `432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf` | Local/ignored |
| HFD_Code_V2.3.bin (official) | 313,652 | `a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03` | Local/ignored |
| UartTFT-II_Flash.bin | 127,599,044 | `4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4` | Local/ignored |

Same-named files must be identified by hash, not filename. `HFD_Code_V2.3.bin` exists in an earlier build (313,504 bytes, `b2778232...`) that differs from the official build above.

---

## 3. Reproduction of `UartTFT-II_Flash.bin`

The ZIP can reproduce `UartTFT-II_Flash.bin` using the softce hash-locked offline extractor (`tools/softce-aula-l99-research/tools/extract_l99_reset_assets.py`). The extractor verifies the screen reset EXE SHA-256 before extraction and stops if the screen EXE's SHA differs, so the extracted `UartTFT-II_Flash.bin` (`4cb3fa5c...`) is traceable to the official ZIP hash above.

This extraction path is offline and read-only; no EXE is executed and no hardware is accessed.

---

## 4. Private backup recommendation

The official ZIP (45,080,624 bytes, SHA-256 `e854bebb...`) is the only authoritative source for factory `UartTFT-II_Flash.bin`, `HFD_Code_V2.2.bin`, and `HFD_Code_V2.3.bin`. A private backup of the ZIP and its extracted assets is strongly recommended, because if aulastar.com replaces the archive, different contents under the same filename are not automatically compatible.

Private backups are local only and must not be committed to Git.

---

## 5. Redistribution policy

Vendor binaries — including the official reset ZIP, screen reset EXE, keyboard reset EXE, `HFD_Code_V2.2.bin`, `HFD_Code_V2.3.bin`, `UartTFT-II_Flash.bin`, `HFD_ISP_TOOL_V1.31.exe`, `L99 ISP V1.23.exe`, and `Flash.ini` — are **not redistributed in the public repository**. Only sizes and SHA-256 values are documented. Third-party repositories (softce/aula-l99-research, gavindi/Aula_L99_Linux, mos9527/evbunpack) are referenced but not vendored.

---

## 6. Confidence

| Finding | Confidence |
|---|---|
| Official ZIP URL, filename, size, SHA-256 | VERIFIED (softce recovery.md) |
| ZIP directory date != release date | VERIFIED (URL path vs package label) |
| ZIP can reproduce UartTFT-II_Flash.bin via hash-locked extractor | STRONG_INFERENCE (extractor logic reviewed statically) |
| Vendor binaries not redistributed | VERIFIED (repository policy + .gitignore) |
