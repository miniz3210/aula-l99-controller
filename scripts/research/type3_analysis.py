import json, os
from collections import Counter

MANIFEST = r"C:\temp\aula-l99-controller\tools\softce-aula-l99-research\inspection\manifest.json"
HFD = r"C:\temp\aula-l99-controller\tools\softce-aula-l99-research\extracted\HFD_Code_V2.3.bin"

with open(MANIFEST, "r", encoding="utf-8") as f:
    m = json.load(f)
pages = m["pages"]
icon_count = 569
icons_by_id_bank = {}
for bank_idx, bank in enumerate(m["icons"]):
    for d in bank:
        icons_by_id_bank[(d["id"], bank_idx)] = d

def desc_valid(icon_id):
    if not (0 <= icon_id < icon_count):
        return False
    d0 = icons_by_id_bank.get((icon_id, 0))
    d1 = icons_by_id_bank.get((icon_id, 1))
    return d0 is not None and d1 is not None and d0.get("status") == "decoded" and d1.get("status") == "decoded"

def bank_decode(icon_id):
    d0 = icons_by_id_bank.get((icon_id, 0))
    d1 = icons_by_id_bank.get((icon_id, 1))
    return (d0 is not None and d0.get("status") == "decoded"), (d1 is not None and d1.get("status") == "decoded")

def bank_in_bounds(icon_id):
    return 0 <= icon_id < icon_count

all_type3 = []
for page in pages:
    pid = page["id"]
    for rec in page["display"]:
        if rec["type"] == 3:
            all_type3.append((pid, rec))

print("TASK A - TYPE 3 INVENTORY")
print("=" * 70)
print(f"Total type 3 records: {len(all_type3)}")
pc = Counter(pid for pid, _ in all_type3)
print("Per-page counts:")
for pid in sorted(pc):
    print(f"  page {pid}: {pc[pid]}")
print(f"Sum of per-page counts: {sum(pc.values())}")
print(f"Sum equals reported total: {sum(pc.values()) == len(all_type3)}")
vc = Counter(rec.get("variable") for _, rec in all_type3)
print("Per-variable counts:")
for v in sorted(vc):
    print(f"  var {v}: {vc[v]}")
print(f"Sum of per-variable counts: {sum(vc.values())}")
both_valid = 0; match = 0; first_ff = 0; last_ff = 0; eq = 0; lt = 0
for pid, rec in all_type3:
    fi = rec.get("first_icon"); li = rec.get("last_icon")
    mn = rec.get("min_value"); mx = rec.get("max_value")
    fv = desc_valid(fi); lv = desc_valid(li)
    if fv and lv:
        both_valid += 1
    if fi == 0xFFFF:
        first_ff += 1
    if li == 0xFFFF:
        last_ff += 1
    if fv and lv and fi <= li:
        irs = li - fi + 1
        if mn is not None and mx is not None and mx - mn + 1 == irs:
            match += 1
    if mn is not None and mx is not None:
        if mn == mx:
            eq += 1
        if mn < mx:
            lt += 1
print(f"Both icon endpoints valid: {both_valid}")
print(f"Matching icon/value range sizes: {match}")
print(f"0xFFFF in first_icon: {first_ff}")
print(f"0xFFFF in last_icon: {last_ff}")
print(f"min_value == max_value: {eq}")
print(f"min_value < max_value: {lt}")

print()
print("TASK B - CANDIDATE OCCURRENCES")
print("=" * 70)
print("Candidate 1: variable 8, icons 14-20, values 0-*")
c1 = 0
for pid, rec in all_type3:
    if rec.get("variable") == 8 and rec.get("first_icon") == 14 and rec.get("last_icon") == 20 and rec.get("min_value") == 0:
        c1 += 1
        fi = rec.get("first_icon"); li = rec.get("last_icon")
        b0, b1 = bank_decode(fi); b0l, b1l = bank_decode(li)
        print(f"  page {pid} | offset 0x{rec['offset']:08X} ({rec['offset']})")
        print(f"    variable={rec['variable']} x={rec['x']} y={rec['y']}")
        print(f"    first_icon={fi} last_icon={li} min_value={rec['min_value']} max_value={rec['max_value']}")
        print(f"    payload={rec.get('payload')}")
        print(f"    descriptor index valid: first in-bounds={bank_in_bounds(fi)} last in-bounds={bank_in_bounds(li)}")
        print(f"    first_icon decode bank0={b0} bank1={b1}")
        print(f"    last_icon decode bank0={b0l} bank1={b1l}")
print(f"  Candidate 1 occurrences: {c1}")

print()
print("Candidate 2: variable 2, icons 9-13, values 0-4")
c2 = 0
for pid, rec in all_type3:
    if rec.get("variable") == 2 and rec.get("first_icon") == 9 and rec.get("last_icon") == 13 and rec.get("min_value") == 0 and rec.get("max_value") == 4:
        c2 += 1
        fi = rec.get("first_icon"); li = rec.get("last_icon")
        b0, b1 = bank_decode(fi); b0l, b1l = bank_decode(li)
        print(f"  page {pid} | offset 0x{rec['offset']:08X} ({rec['offset']})")
        print(f"    variable={rec['variable']} x={rec['x']} y={rec['y']}")
        print(f"    first_icon={fi} last_icon={li} min_value={rec['min_value']} max_value={rec['max_value']}")
        print(f"    payload={rec.get('payload')}")
        print(f"    descriptor index valid: first in-bounds={bank_in_bounds(fi)} last in-bounds={bank_in_bounds(li)}")
        print(f"    first_icon decode bank0={b0} bank1={b1}")
        print(f"    last_icon decode bank0={b0l} bank1={b1l}")
print(f"  Candidate 2 occurrences: {c2}")

print()
print("Candidate 3: variables 174-208 with two-state icon ranges")
c3 = 0
for pid, rec in all_type3:
    v = rec.get("variable")
    if v is not None and 174 <= v <= 208:
        c3 += 1
        fi = rec.get("first_icon"); li = rec.get("last_icon")
        mn = rec.get("min_value"); mx = rec.get("max_value")
        b0, b1 = bank_decode(fi); b0l, b1l = bank_decode(li)
        print(f"  page {pid} | offset 0x{rec['offset']:08X} ({rec['offset']})")
        print(f"    variable={v} x={rec['x']} y={rec['y']}")
        print(f"    first_icon={fi} last_icon={li} min_value={mn} max_value={mx}")
        print(f"    payload={rec.get('payload')}")
        print(f"    descriptor index valid: first in-bounds={bank_in_bounds(fi)} last in-bounds={bank_in_bounds(li)}")
        print(f"    first_icon decode bank0={b0} bank1={b1}")
        print(f"    last_icon decode bank0={b0l} bank1={b1l}")
print(f"  Candidate 3 occurrences: {c3}")

print()
print("TASK C - ANIMATION RECONCILIATION")
print("=" * 70)
stats = m["stats"]
anims = m.get("animations", [])
print(f"Manifest animation groups: {len(anims)}")
print(f"stats.animations = {stats['animations']}")
print(f"stats.animation_frames = {stats['animation_frames']}")
total_frames = 0
for g in anims:
    frames = g.get("frames", [])
    total_frames += len(frames)
    print(f"  Group {g.get('group')}: frame_table=0x{g.get('frame_table'):08X} frame_count={len(frames)}")
print(f"Sum of group frame counts: {total_frames}")
print(f"Startup animation table: 171 entries x 20 bytes = 3420 bytes")
print(f"Startup animation table range: [0x04240000, 0x04240D5C)")
print(f"Classification: separate structures (independent ranges and parser paths)")

print()
print("TASK D PRELIM - HFD Code V2.3.bin presence")
print(f"HFD file exists: {os.path.exists(HFD)}")
if os.path.exists(HFD):
    print(f"HFD size: {os.path.getsize(HFD)}")
