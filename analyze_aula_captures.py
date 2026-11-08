import csv
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

TSHARK = Path(r"C:\Program Files\Wireshark\tshark.exe")
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "capture_analysis"
CAPTURE_GLOB = "aula_*.pcapng"

FIELDS = [
    "frame.number",
    "frame.time_relative",
    "usb.device_address",
    "usb.endpoint_address",
    "frame.len",
    "usb.data_len",
    "usbhid.data",
    "usb.capdata",
    "usbcom.data.out_payload",
]

HID_USAGE_NAMES = {
    0x28: "Enter",
    0x29: "Escape",
    0x2A: "Backspace",
    0x53: "Num Lock",
    0x54: "NumPad /",
    0x55: "NumPad *",
    0x56: "NumPad -",
    0x57: "NumPad +",
    0x58: "NumPad Enter",
    0x59: "NumPad 1 / End",
    0x5A: "NumPad 2 / Down",
    0x5B: "NumPad 3 / PageDown",
    0x5C: "NumPad 4 / Left",
    0x5D: "NumPad 5",
    0x5E: "NumPad 6 / Right",
    0x5F: "NumPad 7 / Home",
    0x60: "NumPad 8 / Up",
    0x61: "NumPad 9 / PageUp",
    0x62: "NumPad 0 / Insert",
    0x63: "NumPad . / Delete",
    0x67: "NumPad =",
}

CONSUMER_USAGE_NAMES = {
    0x00B5: "Next Track",
    0x00B6: "Previous Track",
    0x00B7: "Stop",
    0x00CD: "Play/Pause",
    0x00E2: "Mute",
    0x00E9: "Volume Up",
    0x00EA: "Volume Down",
}


def run_tshark(capture):
    command = [
        str(TSHARK),
        "-r", str(capture),
        "-Y", "usb.data_len > 0",
        "-T", "fields",
        "-E", "separator=|",
        "-E", "quote=n",
        "-E", "occurrence=f",
    ]
    for field in FIELDS:
        command.extend(["-e", field])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"tshark failed for {capture.name}:\n{result.stderr}"
        )

    records = []
    for line in result.stdout.splitlines():
        parts = line.split("|")
        if len(parts) < len(FIELDS):
            parts.extend([""] * (len(FIELDS) - len(parts)))
        row = dict(zip(FIELDS, parts[:len(FIELDS)]))
        try:
            row["frame_number"] = int(row["frame.number"] or 0)
            row["time"] = float(row["frame.time_relative"] or 0)
            row["frame_length"] = int(row["frame.len"] or 0)
            row["data_length"] = int(row["usb.data_len"] or 0)
        except ValueError:
            continue
        row["device"] = row["usb.device_address"]
        row["endpoint"] = row["usb.endpoint_address"].lower()
        row["hid"] = clean_hex(row["usbhid.data"])
        row["capdata"] = clean_hex(row["usb.capdata"])
        row["usbcom_out"] = clean_hex(
            row["usbcom.data.out_payload"]
        )
        row["payload"] = obtain_payload(row)
        records.append(row)
    return records


def clean_hex(value):
    return "".join(ch for ch in (value or "") if ch in "0123456789abcdefABCDEF").lower()


def obtain_payload(row):
    expected = row["data_length"]
    for candidate in (row["hid"], row["capdata"]):
        if candidate and len(candidate) >= expected * 2:
            return candidate[-expected * 2:]
    return ""


def payload_bytes(row):
    try:
        return bytes.fromhex(row["payload"])
    except ValueError:
        return b""


def signed16(data, offset):
    if len(data) < offset + 2:
        return None
    return int.from_bytes(data[offset:offset + 2], "little", signed=True)


def decode_keyboard_report(data):
    if len(data) != 8:
        return None
    modifier = data[0]
    usages = [value for value in data[2:8] if value]
    if not usages and modifier == 0:
        return {"state": "release", "modifier": 0, "usages": [], "names": []}
    names = [HID_USAGE_NAMES.get(value, f"Usage 0x{value:02X}") for value in usages]
    return {"state": "press", "modifier": modifier, "usages": usages, "names": names}


def decode_consumer_report(data):
    if len(data) not in (2, 3, 4, 8):
        return None
    candidates = []
    for offset in range(0, len(data) - 1):
        value = int.from_bytes(data[offset:offset + 2], "little")
        if value in CONSUMER_USAGE_NAMES:
            candidates.append((offset, value, CONSUMER_USAGE_NAMES[value]))
    return candidates


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyse_capture(capture, records):
    capture_dir = OUTPUT_DIR / capture.stem
    capture_dir.mkdir(parents=True, exist_ok=True)

    endpoint_counts = Counter(
        (r["device"], r["endpoint"], r["frame_length"], r["data_length"])
        for r in records
    )
    with (capture_dir / "endpoint_summary.txt").open("w", encoding="utf-8") as out:
        out.write(f"Capture: {capture.name}\n")
        out.write(f"Payload records: {len(records)}\n\n")
        out.write("count|device|endpoint|frame_len|data_len\n")
        for key, count in endpoint_counts.most_common():
            out.write(f"{count}|{key[0]}|{key[1]}|{key[2]}|{key[3]}\n")

    raw_rows = []
    for r in records:
        raw_rows.append({
            "frame": r["frame_number"],
            "time": f"{r['time']:.9f}",
            "device": r["device"],
            "endpoint": r["endpoint"],
            "frame_len": r["frame_length"],
            "data_len": r["data_length"],
            "payload": r["payload"],
        })
    write_csv(
        capture_dir / "all_payloads.csv",
        raw_rows,
        ["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"],
    )

    keyboard_rows = []
    mouse_rows = []
    touch_rows = []
    consumer_rows = []
    large_rows = []

    for r in records:
        data = payload_bytes(r)

        decoded = decode_keyboard_report(data)
        if decoded is not None:
            keyboard_rows.append({
                "frame": r["frame_number"],
                "time": f"{r['time']:.9f}",
                "device": r["device"],
                "endpoint": r["endpoint"],
                "state": decoded["state"],
                "modifier": f"0x{decoded['modifier']:02X}",
                "usage_ids": ",".join(f"0x{x:02X}" for x in decoded["usages"]),
                "names": ", ".join(decoded["names"]),
                "payload": r["payload"],
            })

        consumer = decode_consumer_report(data)
        if consumer:
            for offset, usage, name in consumer:
                consumer_rows.append({
                    "frame": r["frame_number"],
                    "time": f"{r['time']:.9f}",
                    "device": r["device"],
                    "endpoint": r["endpoint"],
                    "offset": offset,
                    "usage": f"0x{usage:04X}",
                    "name": name,
                    "payload": r["payload"],
                })

        if len(data) == 11:
            mouse_rows.append({
                "frame": r["frame_number"],
                "time": f"{r['time']:.9f}",
                "device": r["device"],
                "endpoint": r["endpoint"],
                "dx": signed16(data, 0),
                "dy": signed16(data, 2),
                "button": data[4],
                "field5": data[5],
                "report_type": data[6],
                "field7": data[7],
                "payload": r["payload"],
            })

        if len(data) == 21:
            touch_rows.append({
                "frame": r["frame_number"],
                "time": f"{r['time']:.9f}",
                "device": r["device"],
                "endpoint": r["endpoint"],
                "prefix": data[:5].hex(" "),
                "state_byte": data[5],
                "payload": r["payload"],
            })

        if r["frame_length"] == 2087 or len(data) == 2060:
            large_rows.append({
                "frame": r["frame_number"],
                "time": f"{r['time']:.9f}",
                "device": r["device"],
                "endpoint": r["endpoint"],
                "data_len": r["data_length"],
                "prefix": data[:16].hex(" "),
            })

    write_csv(capture_dir / "keyboard_reports.csv", keyboard_rows,
              ["frame", "time", "device", "endpoint", "state", "modifier", "usage_ids", "names", "payload"])
    write_csv(capture_dir / "consumer_reports.csv", consumer_rows,
              ["frame", "time", "device", "endpoint", "offset", "usage", "name", "payload"])
    write_csv(capture_dir / "mouse_reports.csv", mouse_rows,
              ["frame", "time", "device", "endpoint", "dx", "dy", "button", "field5", "report_type", "field7", "payload"])
    write_csv(capture_dir / "touch_reports.csv", touch_rows,
              ["frame", "time", "device", "endpoint", "prefix", "state_byte", "payload"])
    write_csv(capture_dir / "large_screen_packets.csv", large_rows,
              ["frame", "time", "device", "endpoint", "data_len", "prefix"])

    timing_rows = []
    groups = defaultdict(list)
    for r in records:
        groups[(r["device"], r["endpoint"], r["data_length"])].append(r["time"])
    for key, times in groups.items():
        if len(times) < 3:
            continue
        deltas = [b - a for a, b in zip(times, times[1:]) if b >= a]
        if not deltas:
            continue
        timing_rows.append({
            "device": key[0],
            "endpoint": key[1],
            "data_len": key[2],
            "count": len(times),
            "duration_s": f"{max(times) - min(times):.6f}",
            "median_interval_s": f"{statistics.median(deltas):.6f}",
            "min_interval_s": f"{min(deltas):.6f}",
            "max_interval_s": f"{max(deltas):.6f}",
        })
    timing_rows.sort(key=lambda x: (-x["count"], x["device"], x["endpoint"]))
    write_csv(capture_dir / "timing_summary.csv", timing_rows,
              ["device", "endpoint", "data_len", "count", "duration_s", "median_interval_s", "min_interval_s", "max_interval_s"])

    return {
        "capture": capture.name,
        "size": capture.stat().st_size,
        "records": len(records),
        "keyboard_reports": len(keyboard_rows),
        "keyboard_presses": sum(1 for row in keyboard_rows if row["state"] == "press"),
        "consumer_matches": len(consumer_rows),
        "mouse_reports": len(mouse_rows),
        "touch_reports": len(touch_rows),
        "large_screen_packets": len(large_rows),
        "output_dir": str(capture_dir),
    }


def build_cross_capture_reports(summaries):
    fields = [
        "capture", "size", "records", "keyboard_reports", "keyboard_presses",
        "consumer_matches", "mouse_reports", "touch_reports", "large_screen_packets", "output_dir",
    ]
    write_csv(OUTPUT_DIR / "capture_summary.csv", summaries, fields)
    with (OUTPUT_DIR / "capture_summary.txt").open("w", encoding="utf-8") as out:
        out.write("AULA L99 batch capture analysis\n")
        out.write("================================\n\n")
        for item in summaries:
            out.write(f"Capture: {item['capture']}\n")
            out.write(f"  File bytes:            {item['size']}\n")
            out.write(f"  USB payload records:   {item['records']}\n")
            out.write(f"  Keyboard reports:      {item['keyboard_reports']}\n")
            out.write(f"  Keyboard presses:      {item['keyboard_presses']}\n")
            out.write(f"  Consumer matches:      {item['consumer_matches']}\n")
            out.write(f"  11-byte mouse reports: {item['mouse_reports']}\n")
            out.write(f"  21-byte touch reports: {item['touch_reports']}\n")
            out.write(f"  Large screen packets:  {item['large_screen_packets']}\n\n")


def main():
    if not TSHARK.exists():
        raise FileNotFoundError(f"tshark not found: {TSHARK}")

    captures = sorted(PROJECT_ROOT.glob(CAPTURE_GLOB))
    if not captures:
        raise FileNotFoundError(f"No captures matching {CAPTURE_GLOB} in {PROJECT_ROOT}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []

    print(f"Project root: {PROJECT_ROOT}")
    print(f"tshark: {TSHARK}")
    print(f"Captures: {len(captures)}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    for index, capture in enumerate(captures, start=1):
        print(f"[{index}/{len(captures)}] {capture.name}")
        records = run_tshark(capture)
        summary = analyse_capture(capture, records)
        summaries.append(summary)
        print(
            f"  records={summary['records']}, "
            f"keyboard_presses={summary['keyboard_presses']}, "
            f"mouse={summary['mouse_reports']}, "
            f"touch={summary['touch_reports']}, "
            f"large={summary['large_screen_packets']}"
        )

    build_cross_capture_reports(summaries)
    print()
    print("Analysis complete.")
    print(f"Summary: {OUTPUT_DIR / 'capture_summary.txt'}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


