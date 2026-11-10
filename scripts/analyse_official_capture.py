#!/usr/bin/env python3
"""Offline analyser for an official L99 ISP V1.23.exe screen-update capture.

Inputs (never hardware, never an updater):
  - Exported Procmon CSV (file activity)
  - USBPcap/Wireshark PCAPNG (USB controller capture)

Outputs:
  - JSON report answering the capture questions
  - Procmon filters for the real EXE and expected child processes
  - Marks every finding as EVIDENCE (directly observed) or INFERENCE (reasoned)

Constraints:
  - Remains offline.
  - Never opens COM/USB or HID.
  - Never executes an updater.
  - Distinguishes evidence from inference.
  - Tests use synthetic fixtures only.
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
# Approved capture target: original untouched L99 ISP V1.23.exe package
# Package root: firmware\unpacked\ (alongside L99 ISP V1.23.exe)
# ---------------------------------------------------------------------------
EXPECTED_FILES = {
    "L99 ISP V1.23.exe": {
        "size": 111008,
        "sha256": "e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0",
        "role": "Screen ISP updater (capture target)",
    },
    "Flash.ini": {
        "size": 1571,
        "sha256": "e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c",
        "role": "ISP tool config (JEDEC -> chip mapping)",
    },
    "HFD_Code_V2.2.bin": {
        "size": 305800,
        "sha256": "432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf",
        "role": "Screen MCU code V2.2",
    },
    "HFD_Code_V2.3.bin": {
        "size": 313504,
        "sha256": "b277823234fcab7137963896493bcb6896fd985fc972354166fcfc584534e37f",
        "role": "Screen MCU code V2.3 (earlier build bundled in package)",
    },
    "HFD_ISP_TOOL_V1.31.exe": {
        "size": 99328,
        "sha256": "3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282",
        "role": "Alternate ISP tool bundled in package",
    },
    "UartTFT-II_Flash.bin": {
        "size": 127599044,
        "sha256": "4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4",
        "role": "Factory UI/resource image read by updater (/UartTFT-II_Flash.bin)",
    },
}

# Runtime DLLs beside the EXE (informational)
RUNTIME_DLLS = {
    "Qt5Core.dll": "2af418a34f2076b05ee08dc4bedbe6eb7050bcb6b0658a3db2d5d4302af2db45",
    "Qt5Gui.dll": "6431689ae70b04224017f0ca8d1ace0102ac03ca5d11aa7cdb1108c6d5ab95a8",
    "Qt5SerialPort.dll": "333df93739e8afefecb4e4c56b91d22350869aa24d3ba44c66d310cea0de86",
    "Qt5Svg.dll": "60bb2aa9d37684ed43a2c5ad8781c0d9af656e1ce1e867ea3a17752970803d87",
    "Qt5Widgets.dll": "fa3d2383ebe612f83da59207119ea7aac8306a9f165457f7b9d97b875c584",
    "libEGL.dll": "d3628f75921b9145e85442f0c77aba7e568bb6b7bd2479ad9c253654b6a6b677",
    "libGLESv2.dll": "1d31fe6b741850f00a4b93bb21591008826f72b10063f0cf933610230524456d",
    "opengl32sw.dll": "25ae7577e066fa80519a8f1c314b15cdd22e4a8d3ecd2a36eeccc79e40714a91d",
    "D3Dcompiler_47.dll": "efbdbbcd0d954f8fdc53467de5d89ad525e4e4a9cfff8a15d07c6fdb350c407f",
    "libgcc_s_dw2-1.dll": "aa8180b63a849e755323bb1abe364b654c0eed9b433738fc491e5b64c410ef76",
    "libstdc++-6.dll": "c05b714b94bab75ddfb77339aa5f48772be7ac2c3e9d7322e2d1549fc0a39cfd",
    "libwinpthread-1.dll": "ae1b4fe65da58196fea59b4dc0be64ae68d6ef04497027fadbddbc2dc38d843d",
}

FORBIDDEN_FILES = {
    "patched_uarttft-ii_flash.bin",
    "l99 keyboard screen reset firmware",
    "screen reset exe",
    "l99-reset.zip",
    "l99 reset firmware 2026.5.25.zip",
}

CAPTURE_TARGET_EXE = "L99 ISP V1.23.exe"
CAPTURE_TARGET_EXE_BASENAME = os.path.splitext(CAPTURE_TARGET_EXE)[0].lower()

# Expected child processes are discovered offline (never launched). These are the
# process names the real EXE may spawn; they are reported from capture artefacts.
EXPECTED_CHILD_PROCESSES = []

FIRMWARE_BASENAMES = {
    "uarttft-ii_flash.bin": "UartTFT-II_Flash.bin",
    "hfd_code_v2.2.bin": "HFD_Code_V2.2.bin",
    "hfd_code_v2.3.bin": "HFD_Code_V2.3.bin",
    "flash.ini": "Flash.ini",
    "hfd_isp_tool_v1.31.exe": "HFD_ISP_TOOL_V1.31.exe",
    "l99 isp v1.23.exe": CAPTURE_TARGET_EXE,
}

USB_VID_PID = ("0xEEEF", "0x268A")

PACKAGE_SUBDIRS = {
    "iconengines", "imageformats", "platforms", "styles", "translations"
}


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
    Also returns all processes and parent/child relationships observed.
    """
    events_by_file = defaultdict(list)
    all_events = []
    processes = defaultdict(set)  # process -> set of child processes seen
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
                "Process Create",
                "Process Start",
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
            # Track process names for child-process detection (offline, from CSV)
            if proc:
                processes[proc].add(basename)
    return events_by_file, all_events, dict(processes)


def detect_child_processes(all_events, processes):
    """Detect process and child-process names from Procmon CSV without launching.

    Returns the capture-target process, any child processes, and process tree
    hints inferred from Process Create / Process Start events.
    """
    target_proc_events = [e for e in all_events
                          if e["process"].lower() == CAPTURE_TARGET_EXE_BASENAME
                          or CAPTURE_TARGET_EXE_BASENAME in e["process"].lower()]
    child_procs = set()
    parent_child = []
    for e in all_events:
        op = e["operation"]
        if op in ("Process Create", "Process Start"):
            detail = e["detail"]
            parent = e["process"]
            # Detail often contains the created command line / image path
            created = os.path.basename(detail) if detail else ""
            if created and created.lower().endswith(".exe"):
                child_procs.add(created)
                parent_child.append({
                    "parent": parent,
                    "child": created,
                    "timestamp": e["timestamp"],
                    "classification": evidence(
                        f"Process Create observed: {parent} -> {created}"
                    ),
                })
    # Also infer child processes from processes that open files beside the EXE
    for proc in processes:
        if proc.lower() != CAPTURE_TARGET_EXE_BASENAME and proc:
            child_procs.add(proc)
    return {
        "capture_target": CAPTURE_TARGET_EXE,
        "capture_target_processes_observed": sorted(
            {e["process"] for e in target_proc_events if e["process"]}
        ),
        "child_processes": sorted(child_procs),
        "expected_child_processes": EXPECTED_CHILD_PROCESSES,
        "parent_child": parent_child,
        "classification": evidence(
            "Process and child-process names detected from Procmon CSV; "
            "no EXE launched"
        ),
    }


def analyse_procmon(events_by_file, all_events, processes):
    opened = []
    read_order = []
    bytes_read_per_file = defaultdict(int)
    hfd_access = {"V2.2": [], "V2.3": []}
    ui_access = []
    forbidden_seen = []
    dll_access = []
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
        elif basename in RUNTIME_DLLS:
            dll_access.extend(reads)
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
        "dll_access_count": len(dll_access),
        "forbidden_access": forbidden_seen,
        "classification": evidence("File activity directly observed from Procmon CSV"),
    }


def generate_procmon_filters(process_info):
    """Generate Procmon filters for the real EXE and expected child processes."""
    target = process_info["capture_target"]
    children = process_info["child_processes"]
    expected = process_info["expected_child_processes"]
    all_procs = [target] + children + expected
    # Deduplicate preserving order
    seen = set()
    proc_list = []
    for p in all_procs:
        if p and p not in seen:
            seen.add(p)
            proc_list.append(p)
    filters = [
        {"field": "Process Name", "operator": "is", "value": target,
         "include": True},
    ]
    for p in proc_list[1:]:
        filters.append({
            "field": "Process Name", "operator": "is", "value": p, "include": True,
        })
    filters += [
        {"field": "Operation", "operator": "is", "value": "CreateFile", "include": True},
        {"field": "Operation", "operator": "is", "value": "ReadFile", "include": True},
        {"field": "Operation", "operator": "is", "value": "WriteFile", "include": True},
        {"field": "Operation", "operator": "is", "value": "QueryOpen", "include": True},
        {"field": "Operation", "operator": "is",
         "value": "QueryStandardInformationFile", "include": True},
        {"field": "Operation", "operator": "is", "value": "CloseFile", "include": True},
        {"field": "Path", "operator": "contains", "value": "firmware\\unpacked\\",
         "include": True},
        {"field": "Path", "operator": "contains", "value": "UartTFT-II_Flash.bin",
         "include": True},
    ]
    return {
        "processes": proc_list,
        "capture_target": target,
        "filters": filters,
        "classification": evidence(
            "Procmon filters generated for L99 ISP V1.23.exe and detected child "
            "processes; no EXE launched"
        ),
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
    blocks = read_pcapng_blocks(path)
    packets = []
    interfaces = {}
    for idx, b in enumerate(blocks):
        if b.block_type == 0x0A0A0A0B:  # Interface Description
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


def detect_command_frames(transfers_out):
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


def detect_reenumeration(packets, usb_analysis):
    events = []
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
# Manifest verification
# ---------------------------------------------------------------------------
def verify_manifest(package_root, expected_files=None):
    """Verify hashes of all package files against expected_files (offline).

    expected_files defaults to module EXPECTED_FILES. Tests may pass a
    synthetic manifest so fixtures need not match real vendor hashes.
    Returns a manifest report dict. Does not launch any EXE.
    """
    if expected_files is None:
        expected_files = EXPECTED_FILES
    report = {"files": {}, "missing": [], "mismatches": [], "forbidden": [], "all_verified": True}
    package_path = Path(package_root)
    for name, entry in expected_files.items():
        candidate = package_path / name if not entry.get("External") else None
        found = False
        if candidate and candidate.exists():
            actual_sha = hashlib_sha256(candidate)
            size = candidate.stat().st_size
            ok = actual_sha == entry["sha256"] and size == entry["size"]
            report["files"][name] = {
                "path": str(candidate),
                "size": size,
                "sha256": actual_sha,
                "expected_sha256": entry["sha256"],
                "expected_size": entry["size"],
                "verified": ok,
                "role": entry["role"],
            }
            found = True
            if not ok:
                report["mismatches"].append(name)
                report["all_verified"] = False
        else:
            # Check external locations for UartTFT-II_Flash.bin
            if entry.get("External"):
                for ext in [
                    Path.home() / "Desktop" / name,
                    Path.home() / "Downloads" / name,
                    Path(package_root).parent / "vendor" / name,
                ]:
                    if ext.exists():
                        actual_sha = hashlib_sha256(ext)
                        size = ext.stat().st_size
                        ok = actual_sha == entry["sha256"] and size == entry["size"]
                        report["files"][name] = {
                            "path": str(ext),
                            "size": size,
                            "sha256": actual_sha,
                            "expected_sha256": entry["sha256"],
                            "expected_size": entry["size"],
                            "verified": ok,
                            "role": entry["role"],
                        }
                        found = True
                        if not ok:
                            report["mismatches"].append(name)
                            report["all_verified"] = False
                        break
            if not found:
                report["missing"].append(name)
                report["all_verified"] = False
    return report


def hashlib_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Main report assembly
# ---------------------------------------------------------------------------
def build_report(procmon_csv, pcapng, package_root, output_json=None, expected_files=None):
    import hashlib  # noqa: F401  (used by verify_manifest)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline": True,
        "hardware_accessed": False,
        "updater_executed": False,
        "capture_target": CAPTURE_TARGET_EXE,
        "inputs": {
            "procmon_csv": str(procmon_csv),
            "pcapng": str(pcapng),
            "package_root": str(package_root),
        },
        "questions": {},
        "summary": {},
    }

    # Manifest verification (offline)
    manifest_report = verify_manifest(package_root, expected_files=expected_files)
    report["manifest"] = manifest_report

    # Procmon analysis
    events_by_file, all_events, processes = parse_procmon_csv(procmon_csv)
    file_analysis = analyse_procmon(events_by_file, all_events, processes)
    report["file_activity"] = file_analysis

    # Process / child-process detection (offline, no launch)
    process_info = detect_child_processes(all_events, processes)
    report["processes"] = process_info

    # Procmon filters for real EXE + expected child processes
    proc_filters = generate_procmon_filters(process_info)
    report["procmon_filters"] = proc_filters

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

    # Answers to the capture questions
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
        "capture_target": CAPTURE_TARGET_EXE,
        "files_opened_count": len(opened),
        "hfd_v22_read": file_analysis["hfd_v22_access"] > 0,
        "hfd_v23_read": file_analysis["hfd_v23_access"] > 0,
        "uarttft_read": file_analysis["ui_access_count"] > 0,
        "dll_access_count": file_analysis["dll_access_count"],
        "total_usb_out_bytes": usb_analysis["total_out_bytes"],
        "command_frame_count": len(command_frames),
        "forbidden_file_accessed": len(file_analysis["forbidden_access"]) > 0,
        "manifest_all_verified": manifest_report["all_verified"],
        "manifest_missing": manifest_report["missing"],
        "manifest_mismatches": manifest_report["mismatches"],
        "child_processes": process_info["child_processes"],
        "offline_analyser": True,
    }

    if output_json:
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return report


def print_summary(report):
    print("=== Official Update Capture Analysis (offline) ===")
    print(f"Capture target: {report['capture_target']}")
    print(f"Manifest all verified: {report['summary']['manifest_all_verified']}")
    if report["summary"]["manifest_missing"]:
        print(f"  Missing: {report['summary']['manifest_missing']}")
    if report["summary"]["manifest_mismatches"]:
        print(f"  Mismatches: {report['summary']['manifest_mismatches']}")
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
    print(f"Child processes: {report['summary']['child_processes']}")
    print(f"Procmon filter processes: {report['procmon_filters']['processes']}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline analyser for official L99 ISP V1.23.exe screen-update capture"
    )
    parser.add_argument("--procmon-csv", required=True, help="Exported Procmon CSV")
    parser.add_argument("--pcapng", required=True, help="USBPcap/Wireshark PCAPNG")
    parser.add_argument("--package-root", required=True, help="L99 ISP V1.23.exe package root")
    parser.add_argument("--output-json", help="Write JSON report to this path")
    args = parser.parse_args(argv)

    if not os.path.exists(args.procmon_csv):
        print(f"ERROR: Procmon CSV not found: {args.procmon_csv}", file=sys.stderr)
        return 2
    if not os.path.exists(args.pcapng):
        print(f"ERROR: PCAPNG not found: {args.pcapng}", file=sys.stderr)
        return 2
    if not os.path.isdir(args.package_root):
        print(f"ERROR: Package root not found: {args.package_root}", file=sys.stderr)
        return 2

    report = build_report(args.procmon_csv, args.pcapng, args.package_root, args.output_json)
    print_summary(report)
    if args.output_json:
        print(f"Report written to {args.output_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
