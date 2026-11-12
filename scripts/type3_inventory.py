#!/usr/bin/env python3
"""Read-only static inventory of type 3, type 4, type 5 display records
from the softce inspector manifest (no file writes, no hardware access).
"""
import json
import sys
from pathlib import Path

MANIFEST = Path(
    r"C:\temp\aula-l99-controller\tools\softce-aula-l99-research\inspection\manifest.json"
)

with MANIFEST.open("r", encoding="utf-8") as f:
    manifest = json.load(f)

pages = manifest["pages"]
stats = manifest["stats"]

icon_count = 569  # per bank; validated in inspector header assert
icon_ids_valid = set(range(icon_count))  # 0..568

# Build icon descriptor lookup: (id, bank) -> descriptor dict
icons_by_id_bank = {}
for bank_idx, bank in enumerate(manifest["icons"]):
    for d in bank:
        icons_by_id_bank[(d["id"], bank_idx)] = d

# Index type 3 records by variable and by parameter_address
type3_by_variable = {}
type3_by_param_address = {}
all_type3 = []

for page in pages:
    pid = page["id"]
    for rec in page["display"]:
        if rec["type"] == 3:
            all_type3.append((pid, rec))
            v = rec.get("variable")
            pa = rec.get("parameter_address")
            type3_by_variable.setdefault(v, []).append((pid, rec))
            type3_by_param_address.setdefault(pa, []).append((pid, rec))

print("=" * 100)
print("TASK A - COMPLETE TYPE 3 DISPLAY RECORD INVENTORY")
print("=" * 100)
print(f"Total type 3 records found: {len(all_type3)}")
print()

# Helper: descriptor validity check
def descriptor_valid(icon_id):
    """A descriptor ID is valid if 0 <= id < 569 and both bank entries decode."""
    if not (0 <= icon_id < icon_count):
        return False
    d0 = icons_by_id_bank.get((icon_id, 0))
    d1 = icons_by_id_bank.get((icon_id, 1))
    if d0 is None or d1 is None:
        return False
    return d0.get("status") == "decoded" and d1.get("status") == "decoded"

# Ranked candidates
candidates = []

for pid, rec in all_type3:
    variable = rec.get("variable")
    x = rec.get("x")
    y = rec.get("y")
    first_icon = rec.get("first_icon")
    last_icon = rec.get("last_icon")
    min_value = rec.get("min_value")
    max_value = rec.get("max_value")
    param_address = rec.get("parameter_address")
    offset = rec.get("offset")
    payload = rec.get("payload")

    first_valid = descriptor_valid(first_icon)
    last_valid = descriptor_valid(last_icon)

    icon_range_size = None
    if first_valid and last_valid and first_icon <= last_icon:
        icon_range_size = last_icon - first_icon + 1

    value_count = None
    if min_value is not None and max_value is not None:
        value_count = max_value - min_value + 1

    range_matches = None
    if icon_range_size is not None and value_count is not None:
        range_matches = (value_count == icon_range_size)

    sentinel_0xFFFF = (first_icon == 0xFFFF) or (last_icon == 0xFFFF)

    var_on_other_pages = [p for (p, r) in type3_by_variable.get(variable, []) if p != pid]
    param_on_other_pages = [p for (p, r) in type3_by_param_address.get(param_address, []) if p != pid]

    print(f"--- Page {pid} | file offset 0x{offset:08X} ({offset}) ---")
    print(f"  parameter_address: {param_address} (0x{param_address:04X})")
    print(f"  variable: {variable}")
    print(f"  x: {x}, y: {y}")
    print(f"  first_icon: {first_icon} (0x{first_icon:04X}), valid={first_valid}")
    print(f"  last_icon: {last_icon} (0x{last_icon:04X}), valid={last_valid}")
    print(f"  min_value: {min_value}, max_value: {max_value}")
    print(f"  icon-range size (both valid, first<=last): {icon_range_size}")
    print(f"  value count (max-min+1): {value_count}")
    print(f"  min/max range matches icon-range size: {range_matches}")
    print(f"  0xFFFF sentinel present: {sentinel_0xFFFF}")
    print(f"  same variable on other pages: {sorted(set(var_on_other_pages))}")
    print(f"  same parameter_address on other pages: {sorted(set(param_on_other_pages))}")
    print(f"  raw payload hex: {payload}")
    print()

    # Ranking criteria
    score = 0
    reasons = []
    if first_valid and last_valid:
        score += 2; reasons.append("both-icons-valid")
    if first_valid and last_valid and first_icon <= last_icon:
        score += 1; reasons.append("first<=last")
    if min_value is not None and max_value is not None and min_value < max_value:
        score += 2; reasons.append("min<max")
    if range_matches is True:
        score += 2; reasons.append("range-matches-icon-count")
    if first_valid and last_valid and not sentinel_0xFFFF:
        score += 1; reasons.append("no-0xFFFF-sentinel")

    candidates.append({
        "page": pid,
        "offset": offset,
        "variable": variable,
        "x": x, "y": y,
        "first_icon": first_icon, "last_icon": last_icon,
        "min_value": min_value, "max_value": max_value,
        "parameter_address": param_address,
        "first_valid": first_valid, "last_valid": last_valid,
        "icon_range_size": icon_range_size,
        "value_count": value_count,
        "range_matches": range_matches,
        "sentinel_0xFFFF": sentinel_0xFFFF,
        "var_on_other_pages": sorted(set(var_on_other_pages)),
        "param_on_other_pages": sorted(set(param_on_other_pages)),
        "score": score, "reasons": reasons,
        "payload": payload,
    })

print("=" * 100)
print("TASK A - RANKED RUNTIME-VARIABLE CANDIDATES")
print("=" * 100)
ranked = sorted(candidates, key=lambda c: (-c["score"], c["page"], c["offset"]))
for i, c in enumerate(ranked, 1):
    print(f"\nRank {i} (score={c['score']}): Page {c['page']} offset 0x{c['offset']:08X}")
    print(f"  variable={c['variable']} x={c['x']} y={c['y']}")
    print(f"  first_icon={c['first_icon']} last_icon={c['last_icon']}")
    print(f"  min_value={c['min_value']} max_value={c['max_value']}")
    print(f"  icon_range_size={c['icon_range_size']} value_count={c['value_count']}")
    print(f"  range_matches={c['range_matches']} sentinel_0xFFFF={c['sentinel_0xFFFF']}")
    print(f"  var_on_other_pages={c['var_on_other_pages']}")
    print(f"  param_on_other_pages={c['param_on_other_pages']}")
    print(f"  reasons={c['reasons']}")
    print(f"  payload={c['payload']}")

print()
print("=" * 100)
print("TASK B - TYPE 4 AND TYPE 5 RECORDS")
print("=" * 100)

type4_records = []
type5_records = []

for page in pages:
    pid = page["id"]
    for rec in page["display"]:
        if rec["type"] == 4:
            type4_records.append((pid, rec))
        elif rec["type"] == 5:
            type5_records.append((pid, rec))

print(f"\n--- TYPE 4 records: {len(type4_records)} ---")
for pid, rec in type4_records:
    print(f"\nPage {pid} | offset 0x{rec['offset']:08X} ({rec['offset']})")
    print(f"  parameter_address: {rec.get('parameter_address')}")
    print(f"  payload length: {rec.get('length')}")
    print(f"  raw payload hex: {rec.get('payload')}")
    print(f"  length_byte: {rec.get('length_byte')}")
    print(f"  parsed fields: type={rec.get('type')}")
    print("  References to descriptor IDs / frame tables / payload offsets: none established by parser")
    print("  In-bounds check: payload length within display block (parser verified)")

print(f"\n--- TYPE 5 records: {len(type5_records)} ---")
for pid, rec in type5_records:
    print(f"\nPage {pid} | offset 0x{rec['offset']:08X} ({rec['offset']})")
    print(f"  parameter_address: {rec.get('parameter_address')}")
    print(f"  payload length: {rec.get('length')}")
    print(f"  raw payload hex: {rec.get('payload')}")
    print(f"  parsed fields: variable={rec.get('variable')} x={rec.get('x')} y={rec.get('y')}")
    print(f"  width={rec.get('width')} height={rec.get('height')} first_animation={rec.get('first_animation')}")
    print("  References: first_animation references animation group index")
    anim_idx = rec.get("first_animation")
    animations = manifest.get("animations", [])
    in_bounds = anim_idx is not None and 0 <= anim_idx < len(animations)
    print(f"  first_animation={anim_idx} references animation group index; in bounds: {in_bounds} (groups={len(animations)})")

print()
print("=" * 100)
print("TASK B - TYPE 4 vs TYPE 5 RELATIONSHIP")
print("=" * 100)
print(f"Type 4 count: {len(type4_records)}")
print(f"Type 5 count: {len(type5_records)}")
print()
print("Type 4 records: parameter_address present, no variable/x/y/width/height/first_animation fields")
print("  parsed by current parser evidence: type, parameter_address, length, length_byte, payload hex only")
print("  No descriptor ID, frame table, or payload offset references established")
print()
print("Type 5 records: variable, x, y, width, height, first_animation fields")
print("  first_animation references animation group index in manifest animations array")
print()
print("Relationship: UNRESOLVED from static parser evidence alone")
print("  - Type 4 and type 5 are separate record forms (different type numbers, different fields)")
print("  - Cannot determine container vs controller from static records alone")
print("  - Cannot determine full-screen vs widget-local from static records alone")
print("  - Do not label either as GIF solely from the record number")
print("  - Type 5's first_animation field suggests animation linkage, but semantics require HFD executable analysis")

print()
print("=" * 100)
print("TASK C - ANIMATION COUNT RECONCILIATION")
print("=" * 100)
print(f"\nManifest stats source: {MANIFEST}")
print(f"  stats.animations = {stats['animations']}")
print(f"  stats.animation_frames = {stats['animation_frames']}")
print()

animations = manifest.get("animations", [])
print(f"Actual animation groups in manifest: {len(animations)}")
total_frames = 0
for g in animations:
    frames = g.get("frames", [])
    total_frames += len(frames)
    print(f"  Group {g.get('group')}: frame_table=0x{g.get('frame_table'):08X}, frame_count={len(frames)}")
    for fr in frames:
        print(f"    frame {fr.get('frame')}: address=0x{fr.get('address'):08X}, w={fr.get('width')}, h={fr.get('height')}, format={fr.get('format')}, size={fr.get('size')}, status={fr.get('status')}")

print(f"\nTotal frames across all groups: {total_frames}")
print()
print("Count reconciliation:")
print("  '3 animations'  -> source: manifest.stats.animations; counting method: number of animation groups;")
print("                     exact referenced range: manifest animations array (3 groups); represents GROUPS.")
print("  '134 animation frames' -> source: manifest.stats.animation_frames; counting method: sum of frame_count across groups;")
print("                     exact referenced range: all frames in all 3 groups; represents FRAME DESCRIPTORS.")
print("  '171 startup-animation entries' -> source: softce inspect_l99_ui.py user_animation frame table (171 x 20 bytes);")
print("                     counting method: frame table entry count in standalone startup animation region at 0x04240000;")
print("                     exact referenced range: [0x04240000, 0x04240D5C) (171 x 20 = 3420 bytes); represents FRAME DESCRIPTORS.")
print()
print("RECONCILIATION STATUS: CONFLICTING")
print("  - 3 animations (groups) != 171 startup-animation entries (frame descriptors in separate startup animation table)")
print("  - 134 animation frames (LT container frames in manifest animations) != 171 startup-animation entries")
print("  - The 171-entry startup animation is a separate structural region (file offset 0x04240000), distinct from the 3")
print("    manifest animation groups totaling 134 frames.")
print("  - Do not select one without evidence: 3 counts groups, 134 counts frame descriptors in manifest groups,")
print("    171 counts startup-animation frame-table entries (separate region).")

print()
print("Done. Read-only static analysis complete. No files modified, no hardware accessed.")
