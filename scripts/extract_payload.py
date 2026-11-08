from collections import Counter, defaultdict
from pathlib import Path
import struct

BASE = Path(
    r"C:\Users\Man\Downloads\innoextract-1.9-windows\appEN"
)

INPUT_PATH = BASE / "aula_payload_hex.txt"

chunks = []

for line_number, line in enumerate(
    INPUT_PATH.read_text(encoding="ascii").splitlines(),
    start=1,
):
    value = line.strip().replace(":", "").replace(" ", "")

    if not value:
        continue

    try:
        data = bytes.fromhex(value)
    except ValueError as exc:
        raise SystemExit(
            f"Invalid hex on line {line_number}: {exc}"
        )

    chunks.append(
        {
            "line": line_number,
            "data": data,
        }
    )

print(f"Chunk count: {len(chunks)}")
print(f"Total bytes: {sum(len(x['data']) for x in chunks)}")

length_counts = Counter(len(x["data"]) for x in chunks)

print("\nChunk-length distribution")

for length, count in sorted(length_counts.items()):
    print(f"  {length:5} bytes: {count:3} chunks")

magic_count = sum(
    1 for item in chunks
    if item["data"].startswith(b"\x5A\xA5")
)

print(f"\nChunks starting 5A A5: {magic_count}/{len(chunks)}")

packet_types = defaultdict(list)

print("\nPer-chunk summary")
print(
    "Idx  Line  Length  Magic  Type  "
    "Bytes 2-7          First 24 bytes"
)

for index, item in enumerate(chunks):
    data = item["data"]
    line_number = item["line"]

    magic = data[:2] == b"\x5A\xA5"

    byte_2 = data[2] if len(data) > 2 else None
    byte_3 = data[3] if len(data) > 3 else None

    packet_type = (
        f"{byte_2:02X}{byte_3:02X}"
        if byte_2 is not None and byte_3 is not None
        else "----"
    )

    packet_types[packet_type].append(index)

    bytes_2_7 = (
        data[2:8].hex(" ")
        if len(data) >= 8
        else data[2:].hex(" ")
    )

    print(
        f"{index:3}  "
        f"{line_number:4}  "
        f"{len(data):6}  "
        f"{'YES' if magic else 'NO ':5}  "
        f"{packet_type:4}  "
        f"{bytes_2_7:17}  "
        f"{data[:24].hex(' ')}"
    )

print("\nPacket-type groups")

for packet_type, indices in sorted(packet_types.items()):
    preview = ", ".join(str(x) for x in indices[:12])

    if len(indices) > 12:
        preview += ", ..."

    print(
        f"  Type {packet_type}: "
        f"{len(indices)} chunks "
        f"[{preview}]"
    )

print("\nShort chunks, less than 2060 bytes")

for index, item in enumerate(chunks):
    data = item["data"]

    if len(data) >= 2060:
        continue

    print(f"\nChunk {index}")
    print(f"  Source line: {item['line']}")
    print(f"  Length:      {len(data)}")
    print(f"  Full data:   {data.hex(' ')}")

print("\nFirst packet candidate fields")

first = chunks[0]["data"]

if len(first) >= 23:
    print(f"  Magic:        {first[0:2].hex(' ')}")
    print(f"  Bytes 2-7:    {first[2:8].hex(' ')}")
    print(f"  Value @8:     {struct.unpack_from('<I', first, 8)[0]}")
    print(f"  Value @11:    {struct.unpack_from('<I', first, 11)[0]}")
    print(f"  Width @14:    {struct.unpack_from('<H', first, 14)[0]}")
    print(f"  Height @16:   {struct.unpack_from('<H', first, 16)[0]}")
    print(f"  Byte @18:     {first[18]}")
    print(f"  Value @19:    {struct.unpack_from('<I', first, 19)[0]}")
    print(f"  Last 16:      {first[-16:].hex(' ')}")