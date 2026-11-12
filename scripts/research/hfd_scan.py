import struct
from pathlib import Path

HFD = Path(r"C:\temp\aula-l99-controller\tools\softce-aula-l99-research\extracted\HFD_Code_V2.3.bin")
data = HFD.read_bytes()
size = len(data)
print(f"HFD_Code_V2.3.bin size: {size} bytes (0x{size:X})")

# Values to search (little-endian)
variable_ids = [2, 8] + list(range(174, 209))
icon_ids = list(range(9, 21)) + list(range(117, 197))
type3_len = 14  # 0x0E

# Known offsets / addresses (from manifest structural analysis)
known_offsets = [
    0x00021DD0,   # page table start
    0x00021F38,   # page table end
    0x005C008E,   # background descriptor table start
    0x005C01F6,   # background descriptor table end
    0x00622A84,   # icon descriptor bank 0 base
    0x00624530,   # icon descriptor bank 0 end / bank 1 start
    0x00625FDC,   # icon descriptor bank 1 end
    0x00A355EC,   # UI project 0 end
]
known_addresses = [
    0x60010000,   # image base
    0x60017490,   # startup entry candidate
]

def find_all(needle: bytes):
    """Yield all (overlapping) offsets of needle in data."""
    off = 0
    while True:
        i = data.find(needle, off)
        if i < 0:
            break
        yield i
        off = i + 1

def context(off, needle_len, n=8):
    s = max(0, off - n)
    e = min(size, off + needle_len + n)
    return data[s:e]

def classify(off):
    # Heuristic: code if near a plausible instruction boundary / aligned, data otherwise.
    # Pure heuristic; mark unknown unless structural evidence.
    return "unknown"

needle_global = b""

hits = []

def add_hit(off, label, needle, value_class):
    ctx = context(off, len(needle), 8)
    hits.append((off, label, needle.hex().upper(), value_class, ctx))

# Search u16 LE for variable ids and icon ids
for v in variable_ids + icon_ids:
    needle = struct.pack("<H", v)
    for off in find_all(needle):
        add_hit(off, f"u16={v}", needle, "u16")

# Search u32 LE for variable ids and icon ids
for v in variable_ids + icon_ids:
    needle = struct.pack("<I", v)
    for off in find_all(needle):
        add_hit(off, f"u32={v}", needle, "u32")

# type 3 record length 14 as u16 and u32
for width, label in [(2, "u16=14"), (4, "u32=14")]:
    needle = struct.pack("<H" if width == 2 else "<I", type3_len)
    for off in find_all(needle):
        add_hit(off, label, needle, "u16/u32")

# Known offsets and addresses as u32 LE
for a in known_offsets + known_addresses:
    needle = struct.pack("<I", a)
    for off in find_all(needle):
        add_hit(off, f"u32=0x{a:08X}", needle, "addr")

# Dedup by (offset, label)
seen = set()
deduped = []
for h in hits:
    key = (h[0], h[1])
    if key in seen:
        continue
    seen.add(key)
    deduped.append(h)

deduped.sort()

print()
print(f"Total raw hits (before dedup): {len(hits)}")
print(f"Total unique hits: {len(deduped)}")
print()
print(f"{'Offset':<10} {'Label':<20} {'Needle':<14} {'Class':<10} Context (16 bytes)")
print("-" * 100)
for off, label, needle, vclass, ctx in deduped:
    ctx_hex = " ".join(f"{b:02X}" for b in ctx)
    print(f"0x{off:06X}  {label:<20} {needle:<14} {vclass:<10} {ctx_hex}")
