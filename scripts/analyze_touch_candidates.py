from collections import Counter
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
INPUT = BASE / "touch_candidate_packets.txt"
OUTPUT = BASE / "touch_changes.txt"


records = []

for line_number, line in enumerate(
    INPUT.read_text(encoding="ascii").splitlines(),
    start=1,
):
    parts = line.strip().split("|")

    if len(parts) != 4:
        continue

    frame_text, time_text, length_text, payload_text = parts

    payload_text = (
        payload_text
        .replace(":", "")
        .replace(" ", "")
        .strip()
    )

    if not payload_text:
        continue

    try:
        payload = bytes.fromhex(payload_text)
    except ValueError:
        continue

    if len(payload) != 11:
        continue

    records.append(
        {
            "frame": int(frame_text),
            "time": float(time_text),
            "payload": payload,
        }
    )


print(f"Packets: {len(records)}")

if not records:
    raise SystemExit("No valid 11-byte packets found")


payload_counts = Counter(
    item["payload"]
    for item in records
)

print(f"Unique payloads: {len(payload_counts)}")

print("\nMost common payloads")

for payload, count in payload_counts.most_common(30):
    print(f"{count:5}  {payload.hex(' ')}")


print("\nPer-byte values")

for offset in range(11):
    values = Counter(
        item["payload"][offset]
        for item in records
    )

    formatted = ", ".join(
        f"0x{value:02X}:{count}"
        for value, count in values.most_common(20)
    )

    print(
        f"byte[{offset:02}] "
        f"unique={len(values):3}  {formatted}"
    )


baseline = payload_counts.most_common(1)[0][0]

print(f"\nBaseline: {baseline.hex(' ')}")


change_lines = []

for item in records:
    payload = item["payload"]

    if payload == baseline:
        continue

    changed_offsets = [
        index
        for index, (old, new) in enumerate(
            zip(baseline, payload)
        )
        if old != new
    ]

    line = (
        f"frame={item['frame']}|"
        f"time={item['time']:.6f}|"
        f"changed={','.join(map(str, changed_offsets))}|"
        f"payload={payload.hex(' ')}"
    )

    change_lines.append(line)


OUTPUT.write_text(
    "\n".join(change_lines),
    encoding="ascii",
)

print(f"\nNon-baseline packets: {len(change_lines)}")
print(f"Output: {OUTPUT}")


print("\nFirst 100 non-baseline packets")

for line in change_lines[:100]:
    print(line)


print("\n16-bit little-endian ranges")

for offset in range(10):
    values = [
        int.from_bytes(
            item["payload"][offset:offset + 2],
            "little",
        )
        for item in records
    ]

    print(
        f"u16@{offset:02}: "
        f"min={min(values):5} "
        f"max={max(values):5} "
        f"unique={len(set(values)):4}"
    )