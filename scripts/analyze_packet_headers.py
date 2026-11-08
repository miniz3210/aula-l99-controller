from collections import Counter
from pathlib import Path
import struct


BASE = Path(__file__).resolve().parent.parent
INPUT = BASE / "aula_payload_hex.txt"


def load_chunks():
    chunks = []

    for line_number, line in enumerate(
        INPUT.read_text(encoding="ascii").splitlines(),
        start=1,
    ):
        value = line.strip().replace(":", "").replace(" ", "")

        if not value:
            continue

        chunks.append(
            (line_number, bytes.fromhex(value))
        )

    return chunks


chunks = load_chunks()

print(f"Input: {INPUT}")
print(f"Chunks: {len(chunks)}")
print()

lengths = Counter(len(data) for _, data in chunks)

print("Length distribution")

for length, count in sorted(lengths.items()):
    print(f"  {length:5} bytes: {count}")

print()

full_chunks = [
    (line_number, data)
    for line_number, data in chunks
    if len(data) == 2060
]

print(f"Full 2060-byte chunks: {len(full_chunks)}")
print()

print(
    "Idx  Magic  bytes[2:12]                  "
    "u16@2  u16@4  u16@6  u16@8  tail"
)

for index, (_, data) in enumerate(full_chunks):
    magic = data[:2].hex(" ")

    values = [
        struct.unpack_from("<H", data, offset)[0]
        for offset in (2, 4, 6, 8)
    ]

    print(
        f"{index:3}  "
        f"{magic:5}  "
        f"{data[2:12].hex(' '):29}  "
        f"{values[0]:5}  "
        f"{values[1]:5}  "
        f"{values[2]:5}  "
        f"{values[3]:5}  "
        f"{data[-8:].hex(' ')}"
    )

print()
print("Magic counts")

magic_counts = Counter(
    data[:2]
    for _, data in chunks
)

for magic, count in magic_counts.most_common():
    print(f"  {magic.hex(' '):8}: {count}")

print()
print("Chunks not starting with 5A A5")

for index, (line_number, data) in enumerate(chunks):
    if data.startswith(b"\x5A\xA5"):
        continue

    print(
        f"  chunk={index}, line={line_number}, "
        f"length={len(data)}, "
        f"head={data[:24].hex(' ')}"
    )