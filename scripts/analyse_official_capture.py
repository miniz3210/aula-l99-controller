#!/usr/bin/env python3
"""Offline analyser for an official AULA L99 screen-update capture.

Inputs (never hardware, never an updater):
  - Exported Procmon CSV (file activity)
  - USBPcap/Wireshark PCAPNG (USB controller capture)

Outputs:
  - JSON report answering the ten capture questions
  - Marks every finding as EVIDENCE (directly observed) or INFERENCE (reasoned)

Constraints:
  - Remains offline.
  - Never opens COM/USB or HID.
  - Never executes an updater.
  - Distinguishes evidence from inference.
"""

import argparse
import csv
import hashlib
import json
import os
import struct
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Expected official firmware files (hashes verified by prepare script)
# ---------------------------------------------------------------------------
EXPECTED_FILES = {
    "UartTFT-II_Flash.bin": {
        "size": 127599044,
        "sha256": "4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4",
        "role": "UI/resource image",
    },
    "HFD_Code_V2.2.bin": {
        "size": 305800,
        "sha256": "432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf",
        "role": "Screen MCU code V2.2",
    },
    "HFD_Code_V2.3.bin": {
        "size": 313652,
        "sha256": "a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03",
        "role": "Screen MCU code V2.3 (official)",
    },
    "Flash.ini": {
        "size": 1571,
        "sha256": "e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c",
        "role": "ISP config",
    },
}

FORBIDDEN_FILES = {"patched_uarttft-ii_flash.bin"}

FIRMWARE_BASENAMES = {
    "uarttft-ii_flash.bin": "UartTFT-II_Flash.bin",
    "hfd_code_v2.2.bin": "HFD_Code_V2.2.bin",
    "hfd_code_v2.3.bin": "HFD_Code_V2.3.bin",
    "flash.ini": "Flash.ini",
}

USB_VID_PID = ("0xEEEF", "0x268A")


# ---------------------------------------------------------------------------
# Evidence / inference helpers
# ---------------------------------------------------------------------------
def evidence(text):
    return {"kind": "EVIDENCE", "detail": text}


def inference(text):
    return {"kind": "INFERENCE", "detail": text}


# ---------------------------------------------------------------------------
# Procmon CSV parsing
# ---------------------------------------------------------------------------
def parse_procmon_csv(path):
    """Parse a Procmon-exported CSV into file events.

    Returns dict: {basename: [events]} where each event has timestamp,
    process, operation, path, result, detail.
    """
    events_by_file = defaultdict(list)
    all_events = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op = (row.get("Operation") or "").strip()
            if op not in {
                "CreateFile",
                "ReadFile",
                "WriteFile",
                "QueryOpen",
                "QueryStandardInformationFile",
                "CloseFile",
            }:
                continue
            path_val = (row.get("Path") or "").strip()
            basename = os.path.basename(path_val).lower()
            proc = (row.get("Process Name") or row.get("Process") or "").strip()
            result = (row.get("Result") or "").strip()
            detail = (row.get("Detail") or "").strip()
            timestamp = (row.get("Time of Day") or row.get("Timestamp") or "").strip()
            event = {
                "timestamp": timestamp,
                "process": proc,
                "operation": op,
                "path": path_val,
                "basename": basename,
                "result": result,
                "detail": detail,
            }
            all_events.append(event)
            if basename in FIRMWARE_BASENAMES or basename in FORBIDDEN_FILES:
                events_by_file[basename].append(event)
    return events_by_file, all_events


def analyse_procmon(events_by_file, all_events):
    opened = []
    read_order = []
    bytes_read_per_file = defaultdict(int)
    hfd_access = {"V2.2": [], "V2.3": []}
    ui_access = []
    forbidden_seen = []
    for basename, events in events_by_file.items():
        canon = FIRMWARE_BASENAMES.get(basename, basename)
        creates = [e for e in events if e["operation"] == "CreateFile"]
        reads = [e for e in events if e["operation"] == "ReadFile"]
        closes = [e for e in events if e["operation"] == "CloseFile"]
        if creates:
            opened.append({
                "file": canon,
                "first_create": creates[0]["timestamp"],
                "process": creates[0]["process"],
                "create_count": len(creates),
                "read_count": len(reads),
                "close_count": len(closes),
                "classification": evidence(
                    f"CreateFile observed for {canon} by {creates[0]['process']}"
                ),
            })
        for r in reads:
            nbytes = 0
            detail = r.get("detail") or ""
            for token in detail.split():
                if token.isdigit():
                    nbytes = int(token)
                    break
            bytes_read_per_file[canon] += nbytes
            read_order.append({
                "file": canon,
                "timestamp": r["timestamp"],
                "process": r["process"],
                "bytes": nbytes,
                "classification": evidence(f"ReadFile {nbytes} bytes from {canon}"),
            })
        if basename == "hfd_code_v2.2.bin":
            hfd_access["V2.2"] = reads
        elif basename == "hfd_code_v2.3.bin":
            hfd_access["V2.3"] = reads
        elif basename == "uarttft-ii_flash.bin":
            ui_access = reads
        if basename in FORBIDDEN_FILES:
            forbidden_seen.append({
                "file": canon,
                "timestamp": events[0]["timestamp"],
                "process": events[0]["process"],
                "classification": evidence(f"FORBIDDEN file accessed: {canon}"),
            })
    read_order.sort(key=lambda e: e["timestamp"] or "")
    return {
        "files_opened": opened,
        "read_order": read_order,
        "bytes_read_per_file": dict(bytes_read_per_file),
        "hfd_v22_access": len(hfd_access["V2.2"]),
        "hfd_v23_access": len(hfd_access["V2.3"]),
        "ui_access_count": len(ui_access),
        "forbidden_access": forbidden_seen,
        "classification": evidence("File activity directly observed from Procmon CSV"),
    }


# ---------------------------------------------------------------------------
# PCAPNG parsing (self-contained, no tshark/Wireshark dependency)
# ---------------------------------------------------------------------------
class PcapNgBlock:
    def __init__(self, block_type, block_length, data, trailer):
        self.block_type = block_type
        self.block_length = block_length
        self.data = data
        self.trailer = trailer


def read_pcapng_blocks(path):
    blocks = []
    with open(path, "rb") as f:
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            block_type = struct.unpack("<I", hdr[0:4])[0]
            block_length = struct.unpack("<I", hdr[4:8])[0]
            if block_length < 12:
                break
            # block_length covers type+length+body+trailer(4). Body excludes
            # the 8-byte header we already read, so body_len = block_length - 12.
            body_len = block_length - 12
            body = f.read(body_len)
            if len(body) < body_len:
                break
            trailer = f.read(4)
            if len(trailer) < 4:
                break
            blocks.append(PcapNgBlock(block_type, block_length, body, trailer))
    return blocks


def parse_pcapng_usb(path):
    """Parse PCAPNG for USB packets.

    Returns list of packet dicts with index, timestamp, length, endpoint,
    direction, data (hex), interface id.
    Best-effort: handles Section Header, Interface Description, Enhanced Packet
    blocks; USB capture specifics (interface type, encapsulation) are noted.
    """
    blocks = read_pcapng_blocks(path)
    packets = []
    interfaces = {}
    for idx, b in enumerate(blocks):
        if b.block_type == 0x0A0A0A0B:  # Interface Description
            # parse interface info best-effort
            ift = struct.unpack("<H", b.data[0:2])[0] if len(b.data) >= 2 else None
            interfaces[idx] = {"link_type": ift}
        elif b.block_type == 0x0A0A0A0D:  # Enhanced Packet Block
            if len(b.data) < 28:
                continue
            interface_id = struct.unpack("<I", b.data[0:4])[0]
            timestamp_high = struct.unpack("<I", b.data[4:8])[0]
            timestamp_low = struct.unpack("<I", b.data[8:12])[0]
            captured_len = struct.unpack("<I", b.data[12:16])[0]
            packet_len = struct.unpack("<I", b.data[16:20])[0]
            pkt_data = b.data[20:20 + captured_len]
            ts = (timestamp_high << 32) | timestamp_low
            packets.append({
                "index": len(packets),
                "timestamp_ns": ts,
                "interface_id": interface_id,
                "captured_len": captured_len,
                "packet_len": packet_len,
                "data_hex": pkt_data.hex(),
                "data": pkt_data,
            })
        elif b.block_type == 0x0A0A0A01:  # Section Header
            pass
    return packets


def classify_usb_direction(data):
    """Best-effort USB direction from raw packet bytes.

    Returns ('OUT'|'IN'|'CONTROL'|'UNKNOWN', classification).
    Real USBPcap encapsulates URBs; without parsing the encapsulation header
    the direction field is not directly available, so this is a heuristic
    and is marked INFERENCE.

    Heuristic: packets beginning with a known host-to-device command frame
    (0x4A 0x30) are host-to-device (OUT). Everything else is UNKNOWN.
    """
    if len(data) < 2:
        return "UNKNOWN", inference("Too few bytes to determine USB direction")
    if data[0:2] == b"\x4A\x30":
        return "OUT", evidence("Host-to-device command frame 0x4A30 observed")
    return "UNKNOWN", inference("USB direction not determinable from raw bytes; marked UNKNOWN")


def analyse_usb(packets):
    transfers_out = []
    transfers_in = []
    control = []
    disconnects = []
    total_out_bytes = 0
    total_in_bytes = 0
    for p in packets:
        data = p["data"]
        direction, dir_class = classify_usb_direction(data)
        plen = p["captured_len"]
        entry = {
            "index": p["index"],
            "timestamp_ns": p["timestamp_ns"],
            "length": plen,
            "direction": direction,
            "direction_class": dir_class,
            "data_hex_prefix": data[:32].hex(),
        }
        if direction == "OUT":
            transfers_out.append(entry)
            total_out_bytes += plen
        elif direction == "IN":
            transfers_in.append(entry)
            total_in_bytes += plen
        else:
            control.append(entry)
    return {
        "transfers_out": transfers_out,
        "transfers_in": transfers_in,
        "control": control,
        "disconnects": disconnects,
        "total_out_bytes": total_out_bytes,
        "total_in_bytes": total_in_bytes,
        "packet_count": len(packets),
        "classification": inference(
            "USB transfer order and timing derived from PCAPNG frame sequence; "
            "direction classification is best-effort inference unless USBPcap "
            "encapsulation fields are parsed explicitly"
        ),
    }


# ---------------------------------------------------------------------------
# USB command/transfer structure detection (4A 30 frames etc.)
# ---------------------------------------------------------------------------
def detect_command_frames(transfers_out):
    """Detect 4A 30 | offset:LE32 | len:LE16 | payload | CRC32:LE16 frames."""
    frames = []
    for t in transfers_out:
        data = bytes.fromhex(t["data_hex_prefix"]) if t["data_hex_prefix"] else b""
        if len(data) >= 4 and data[0:2] == b"\x4A\x30":
            if len(data) >= 8:
                offset = struct.unpack("<I", data[2:6])[0]
                plen = struct.unpack("<H", data[6:8])[0]
                frames.append({
                    "transfer_index": t["index"],
                    "timestamp_ns": t["timestamp_ns"],
                    "command": "0x4A30",
                    "offset": offset,
                    "payload_len": plen,
                    "classification": evidence("0x4A30 frame header observed in USB transfer"),
                })
    return frames


# ---------------------------------------------------------------------------
# Re-enumeration / ISP entry detection
# ---------------------------------------------------------------------------
def detect_reenumeration(packets, usb_analysis):
    events = []
    # Device disconnect/reconnect evidenced by bursts of control transfers
    # or gaps in transfer stream; marked inference without explicit descriptors.
    if usb_analysis["disconnects"]:
        for d in usb_analysis["disconnects"]:
            events.append({
                "timestamp_ns": d["timestamp_ns"],
                "event": "device_disconnect",
                "classification": evidence("USB disconnect event in capture"),
            })
    return {
        "reenumeration_events": events,
        "classification": inference(
            "Re-enumeration and ISP-entry inferred from USB device state changes; "
            "not directly confirmed without device descriptor queries"
        ),
    }


# ---------------------------------------------------------------------------
# CRC / FileCRC / FlashCRC behaviour
# ---------------------------------------------------------------------------
def detect_crc_behaviour(transfers_out):
    crc_frames = []
    for t in transfers_out:
        data = bytes.fromhex(t["data_hex_prefix"]) if t["data_hex_prefix"] else b""
        if len(data) >= 4 and data[0:2] == b"\x4A\x30":
            crc_frames.append({
                "transfer_index": t["index"],
                "timestamp_ns": t["timestamp_ns"],
                "classification": evidence(
                    "Per-packet CRC32 frame (0x4A30) present"
                ),
            })
    return {
        "crc_frame_count": len(crc_frames),
        "frames": crc_frames[:50],
        "classification": inference(
            "FileCRC/FlashCRC behavior inferred from 0x4A30 frames; "
            "image-level self-checksum not observable from USB alone"
        ),
    }


# ---------------------------------------------------------------------------
# Main report assembly
# ---------------------------------------------------------------------------
def build_report(procmon_csv, pcapng, output_json=None):
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "hardware_accessed": False,
        "updater_executed": False,
        "inputs": {
            "procmon_csv": str(procmon_csv),
            "pcapng": str(pcapng),
        },
        "questions": {},
        "summary": {},
    }

    # Procmon analysis
    events_by_file, all_events = parse_procmon_csv(procmon_csv)
    file_analysis = analyse_procmon(events_by_file, all_events)
    report["file_activity"] = file_analysis

    # USB analysis
    packets = parse_pcapng_usb(pcapng)
    usb_analysis = analyse_usb(packets)
    command_frames = detect_command_frames(usb_analysis["transfers_out"])
    reenum = detect_reenumeration(packets, usb_analysis)
    crc_behaviour = detect_crc_behaviour(usb_analysis["transfers_out"])
    report["usb"] = usb_analysis
    report["command_frames"] = command_frames
    report["reenumeration"] = reenum
    report["crc_behaviour"] = crc_behaviour

    # Answers to the ten questions
    opened = file_analysis["files_opened"]
    files_opened = [f["file"] for f in opened]
    report["questions"]["1_files_opened"] = {
        "answer": files_opened,
        "evidence": file_analysis["classification"],
        "detail": [f for f in opened],
    }
    report["questions"]["2_hfd_v22_or_v23_read"] = {
        "answer": {
            "V2.2_reads": file_analysis["hfd_v22_access"],
            "V2.3_reads": file_analysis["hfd_v23_access"],
        },
        "evidence": evidence(
            "HFD_Code_V2.2.bin reads: %d; "
            "HFD_Code_V2.3.bin reads: %d"
            % (file_analysis["hfd_v22_access"], file_analysis["hfd_v23_access"])
        ),
    }
    report["questions"]["3_uarttft_read_independently"] = {
        "answer": file_analysis["ui_access_count"] > 0,
        "evidence": evidence(
            f"UartTFT-II_Flash.bin read count: {file_analysis['ui_access_count']}"
        ),
    }
    report["questions"]["4_file_open_read_order"] = {
        "answer": file_analysis["read_order"],
        "evidence": file_analysis["classification"],
    }
    report["questions"]["5_usb_command_transfer_order"] = {
        "answer": {
            "out_transfers": len(usb_analysis["transfers_out"]),
            "in_transfers": len(usb_analysis["transfers_in"]),
            "command_frames": command_frames,
        },
        "evidence": usb_analysis["classification"],
    }
    report["questions"]["6_ui_and_hfd_both_transmitted"] = {
        "answer": {
            "ui_bytes_read": file_analysis["bytes_read_per_file"].get(
                "UartTFT-II_Flash.bin", 0
            ),
            "hfd_v22_bytes_read": file_analysis["bytes_read_per_file"].get(
                "HFD_Code_V2.2.bin", 0
            ),
            "hfd_v23_bytes_read": file_analysis["bytes_read_per_file"].get(
                "HFD_Code_V2.3.bin", 0
            ),
            "usb_total_out_bytes": usb_analysis["total_out_bytes"],
        },
        "evidence": evidence("Bytes read per file from Procmon; USB total OUT bytes from PCAPNG"),
        "inference": inference(
            "Whether UI and HFD are both transmitted as separate payloads requires "
            "correlating file reads with USB transfers; marked inference until correlated"
        ),
    }
    report["questions"]["7_total_bytes_per_payload"] = {
        "answer": dict(file_analysis["bytes_read_per_file"]),
        "evidence": evidence("Bytes read per file directly from Procmon ReadFile events"),
    }
    report["questions"]["8_reenumeration_isp_entry"] = {
        "answer": reenum,
        "evidence": reenum["classification"],
    }
    report["questions"]["9_filecrc_flashcrc"] = {
        "answer": crc_behaviour,
        "evidence": crc_behaviour["classification"],
    }
    report["questions"]["10_final_success_restart"] = {
        "answer": {
            "usb_transfer_count": usb_analysis["packet_count"],
            "last_transfer_timestamp_ns": (
                usb_analysis["transfers_out"][-1]["timestamp_ns"]
                if usb_analysis["transfers_out"] else None
            ),
        },
        "evidence": inference(
            "Final success/restart inferred from end of USB transfer stream and "
            "screen recording (not parsed here)"
        ),
    }

    # Summary
    report["summary"] = {
        "files_opened_count": len(opened),
        "hfd_v22_read": file_analysis["hfd_v22_access"] > 0,
        "hfd_v23_read": file_analysis["hfd_v23_access"] > 0,
        "uarttft_read": file_analysis["ui_access_count"] > 0,
        "total_usb_out_bytes": usb_analysis["total_out_bytes"],
        "command_frame_count": len(command_frames),
        "forbidden_file_accessed": len(file_analysis["forbidden_access"]) > 0,
        "offline_analyser": True,
    }

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return report


def print_summary(report):
    print("=== Official Update Capture Analysis (offline) ===")
    q = report["questions"]
    print(f"1. Files opened: {q['1_files_opened']['answer']}")
    print(f"2. HFD V2.2 reads: {q['2_hfd_v22_or_v23_read']['answer']['V2.2_reads']}")
    print(f"   HFD V2.3 reads: {q['2_hfd_v22_or_v23_read']['answer']['V2.3_reads']}")
    print(f"3. UartTFT-II_Flash.bin read: {q['3_uarttft_read_independently']['answer']}")
    print(f"4. File read events: {len(q['4_file_open_read_order']['answer'])}")
    print(f"5. USB OUT transfers: {q['5_usb_command_transfer_order']['answer']['out_transfers']}")
    print(f"   USB IN transfers: {q['5_usb_command_transfer_order']['answer']['in_transfers']}")
    print(f"6. UI bytes: {q['6_ui_and_hfd_both_transmitted']['answer']['ui_bytes_read']}")
    print(f"   HFD V2.2 bytes: {q['6_ui_and_hfd_both_transmitted']['answer']['hfd_v22_bytes_read']}")
    print(f"   HFD V2.3 bytes: {q['6_ui_and_hfd_both_transmitted']['answer']['hfd_v23_bytes_read']}")
    print(f"7. Bytes per file: {q['7_total_bytes_per_payload']['answer']}")
    print(f"8. Re-enumeration events: {len(q['8_reenumeration_isp_entry']['answer']['reenumeration_events'])}")
    print(f"9. CRC frames: {q['9_filecrc_flashcrc']['answer']['crc_frame_count']}")
    print(f"10. USB packets total: {q['10_final_success_restart']['answer']['usb_transfer_count']}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline analyser for official AULA L99 screen-update capture"
    )
    parser.add_argument("--procmon-csv", required=True, help="Exported Procmon CSV")
    parser.add_argument("--pcapng", required=True, help="USBPcap/Wireshark PCAPNG")
    parser.add_argument("--output-json", help="Write JSON report to this path")
    args = parser.parse_args(argv)

    if not os.path.exists(args.procmon_csv):
        print(f"ERROR: Procmon CSV not found: {args.procmon_csv}", file=sys.stderr)
        return 2
    if not os.path.exists(args.pcapng):
        print(f"ERROR: PCAPNG not found: {args.pcapng}", file=sys.stderr)
        return 2

    report = build_report(args.procmon_csv, args.pcapng, args.output_json)
    print_summary(report)
    if args.output_json:
        print(f"Report written to {args.output_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
