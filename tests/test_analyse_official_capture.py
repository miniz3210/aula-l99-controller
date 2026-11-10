#!/usr/bin/env python3
"""Synthetic tests for scripts/analyse_official_capture.py.

All fixtures are generated in memory / temp files. No vendor firmware,
no hardware, no updater execution, no COM/USB access.
"""

import csv
import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import analyse_official_capture as mod

PROC_COLUMNS = [
    "Time of Day", "Process Name", "Operation", "Path", "Result", "Detail",
]


def write_procmon_csv(tmpdir, rows, name="procmon.csv"):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(PROC_COLUMNS)
        for row in rows:
            writer.writerow(row)
    return path


def procmon_row(time, proc, op, path, result="SUCCESS", detail=""):
    return [time, proc, op, path, result, detail]


def write_pcapng(tmpdir, packets, name="capture.pcapng"):
    """Write minimal PCAPNG with Section Header, Interface Description,
    and Enhanced Packet Blocks."""
    path = os.path.join(tmpdir, name)
    with open(path, "wb") as f:
        # Section Header Block (type 0x0A0A0A01)
        shb = struct.pack("<II", 0x0A0A0A01, 28)
        f.write(shb)
        f.write(struct.pack("<I", 0x1A2B3C4D))  # magic
        f.write(struct.pack("<H", 1))  # version major
        f.write(struct.pack("<H", 4))  # version minor
        f.write(b"\x00" * 8)  # section length -1
        f.write(struct.pack("<I", 28))  # trailer
        # Interface Description Block (type 0x0A0A0A02), block_length=16
        idb = struct.pack("<II", 0x0A0A0A02, 16)
        f.write(idb)
        f.write(struct.pack("<H", 1))  # link type
        f.write(struct.pack("<H", 0))  # reserved
        f.write(struct.pack("<I", 16))  # trailer
        for data in packets:
            # Enhanced Packet Block: block_length = 4(type)+4(len)+20(body fields)+data+4(trailer)
            blen = 32 + len(data)
            epb = struct.pack("<II", 0x0A0A0A0D, blen)
            f.write(epb)
            f.write(struct.pack("<I", 0))  # interface id
            f.write(struct.pack("<I", 0))  # timestamp high
            f.write(struct.pack("<I", 0))  # timestamp low
            f.write(struct.pack("<I", len(data)))  # captured len
            f.write(struct.pack("<I", len(data)))  # packet len
            f.write(data)
            f.write(struct.pack("<I", blen))  # trailer
    return path


def usb_frame_4a30(offset, payload_len, payload=b""):
    frame = b"\x4A\x30" + struct.pack("<I", offset) + struct.pack("<H", payload_len)
    frame += payload[:payload_len]
    frame += struct.pack("<I", 0xDEADBEEF)  # placeholder CRC
    return frame


class ParseProcmonTests(unittest.TestCase):
    def test_parse_filters_correct_operations(self):
        tmpdir = tempfile.mkdtemp()
        rows = [
            procmon_row("10:00:01", "updater.exe", "CreateFile", r"C:\pkg\UartTFT-II_Flash.bin"),
            procmon_row("10:00:02", "updater.exe", "ReadFile", r"C:\pkg\UartTFT-II_Flash.bin", detail="4096"),
            procmon_row("10:00:03", "updater.exe", "CloseFile", r"C:\pkg\UartTFT-II_Flash.bin"),
            procmon_row("10:00:04", "updater.exe", "Process Create", r"C:\pkg\updater.exe"),
        ]
        path = write_procmon_csv(tmpdir, rows)
        events_by_file, all_events = mod.parse_procmon_csv(path)
        self.assertEqual(len(all_events), 3)
        self.assertIn("uarttft-ii_flash.bin", events_by_file)
        self.assertEqual(len(events_by_file["uarttft-ii_flash.bin"]), 3)

    def test_forbidden_file_flagged(self):
        tmpdir = tempfile.mkdtemp()
        rows = [
            procmon_row("10:00:01", "updater.exe", "CreateFile", r"C:\pkg\patched_UartTFT-II_Flash.bin"),
        ]
        path = write_procmon_csv(tmpdir, rows)
        events_by_file, _ = mod.parse_procmon_csv(path)
        self.assertIn("patched_uarttft-ii_flash.bin", events_by_file)


class AnalyseProcmonTests(unittest.TestCase):
    def test_file_opened_and_read_order(self):
        tmpdir = tempfile.mkdtemp()
        rows = [
            procmon_row("10:00:01", "updater.exe", "CreateFile", r"C:\pkg\HFD_Code_V2.3.bin"),
            procmon_row("10:00:02", "updater.exe", "ReadFile", r"C:\pkg\HFD_Code_V2.3.bin", detail="313652"),
            procmon_row("10:00:03", "updater.exe", "CloseFile", r"C:\pkg\HFD_Code_V2.3.bin"),
            procmon_row("10:00:04", "updater.exe", "CreateFile", r"C:\pkg\UartTFT-II_Flash.bin"),
            procmon_row("10:00:05", "updater.exe", "ReadFile", r"C:\pkg\UartTFT-II_Flash.bin", detail="127599044"),
            procmon_row("10:00:06", "updater.exe", "CloseFile", r"C:\pkg\UartTFT-II_Flash.bin"),
        ]
        path = write_procmon_csv(tmpdir, rows)
        events_by_file, _ = mod.parse_procmon_csv(path)
        result = mod.analyse_procmon(events_by_file, [])
        self.assertEqual(len(result["files_opened"]), 2)
        self.assertEqual(result["files_opened"][0]["file"], "HFD_Code_V2.3.bin")
        self.assertEqual(result["files_opened"][1]["file"], "UartTFT-II_Flash.bin")
        self.assertEqual(result["hfd_v23_access"], 1)
        self.assertEqual(result["hfd_v22_access"], 0)
        self.assertEqual(result["ui_access_count"], 1)
        self.assertEqual(result["bytes_read_per_file"]["HFD_Code_V2.3.bin"], 313652)
        self.assertEqual(result["bytes_read_per_file"]["UartTFT-II_Flash.bin"], 127599044)
        self.assertEqual(result["classification"]["kind"], "EVIDENCE")

    def test_read_order_sorted(self):
        tmpdir = tempfile.mkdtemp()
        rows = [
            procmon_row("10:00:05", "updater.exe", "ReadFile", r"C:\pkg\UartTFT-II_Flash.bin", detail="100"),
            procmon_row("10:00:01", "updater.exe", "ReadFile", r"C:\pkg\HFD_Code_V2.2.bin", detail="50"),
        ]
        path = write_procmon_csv(tmpdir, rows)
        events_by_file, _ = mod.parse_procmon_csv(path)
        result = mod.analyse_procmon(events_by_file, [])
        order = result["read_order"]
        self.assertEqual(order[0]["file"], "HFD_Code_V2.2.bin")
        self.assertEqual(order[1]["file"], "UartTFT-II_Flash.bin")


class PcapNgTests(unittest.TestCase):
    def test_parse_pcapng_enhanced_packet_blocks(self):
        tmpdir = tempfile.mkdtemp()
        packets = [b"\x00" * 64, b"\x00" * 128]
        path = write_pcapng(tmpdir, packets)
        parsed = mod.parse_pcapng_usb(path)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["captured_len"], 64)
        self.assertEqual(parsed[1]["captured_len"], 128)

    def test_parse_empty_pcapng(self):
        tmpdir = tempfile.mkdtemp()
        path = write_pcapng(tmpdir, [])
        parsed = mod.parse_pcapng_usb(path)
        self.assertEqual(parsed, [])


class UsbAnalysisTests(unittest.TestCase):
    def test_transfer_counts_and_bytes(self):
        transfers = [
            usb_frame_4a30(0, 64),
            usb_frame_4a30(64, 2060),
        ]
        packets = []
        for i, data in enumerate(transfers):
            packets.append({
                "index": i, "timestamp_ns": i + 1, "interface_id": 0,
                "captured_len": len(data), "packet_len": len(data),
                "data_hex": data.hex(), "data": data,
            })
        result = mod.analyse_usb(packets)
        self.assertEqual(result["packet_count"], 2)
        self.assertEqual(result["total_out_bytes"], sum(len(d) for d in transfers))
        self.assertEqual(result["classification"]["kind"], "INFERENCE")

    def test_detect_command_frames(self):
        transfers_out = [
            {"index": 0, "timestamp_ns": 1, "length": 2060,
             "data_hex_prefix": usb_frame_4a30(0x1000, 16).hex()},
            {"index": 1, "timestamp_ns": 2, "length": 64, "data_hex_prefix": (b"\x00" * 64).hex()},
        ]
        frames = mod.detect_command_frames(transfers_out)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["command"], "0x4A30")
        self.assertEqual(frames[0]["offset"], 0x1000)
        self.assertEqual(frames[0]["payload_len"], 16)
        self.assertEqual(frames[0]["classification"]["kind"], "EVIDENCE")


class CrcBehaviourTests(unittest.TestCase):
    def test_crc_frame_count(self):
        transfers_out = [
            {"index": 0, "timestamp_ns": 1, "data_hex_prefix": usb_frame_4a30(0, 16).hex()},
            {"index": 1, "timestamp_ns": 2, "data_hex_prefix": usb_frame_4a30(16, 16).hex()},
        ]
        result = mod.detect_crc_behaviour(transfers_out)
        self.assertEqual(result["crc_frame_count"], 2)
        self.assertEqual(result["classification"]["kind"], "INFERENCE")


class BuildReportTests(unittest.TestCase):
    def test_full_report_structure(self):
        tmpdir = tempfile.mkdtemp()
        proc_rows = [
            procmon_row("10:00:01", "updater.exe", "CreateFile", r"C:\pkg\UartTFT-II_Flash.bin"),
            procmon_row("10:00:02", "updater.exe", "ReadFile", r"C:\pkg\UartTFT-II_Flash.bin", detail="127599044"),
            procmon_row("10:00:03", "updater.exe", "CloseFile", r"C:\pkg\UartTFT-II_Flash.bin"),
        ]
        proc_path = write_procmon_csv(tmpdir, proc_rows)
        usb_packets = [usb_frame_4a30(0, 16)]
        pcap_path = write_pcapng(tmpdir, usb_packets)
        out_path = os.path.join(tmpdir, "report.json")

        report = mod.build_report(proc_path, pcap_path, out_path)
        self.assertTrue(report["offline"])
        self.assertFalse(report["hardware_accessed"])
        self.assertFalse(report["updater_executed"])
        self.assertTrue(os.path.exists(out_path))

        q = report["questions"]
        self.assertEqual(q["1_files_opened"]["answer"], ["UartTFT-II_Flash.bin"])
        self.assertEqual(q["2_hfd_v22_or_v23_read"]["answer"]["V2.2_reads"], 0)
        self.assertEqual(q["2_hfd_v22_or_v23_read"]["answer"]["V2.3_reads"], 0)
        self.assertTrue(q["3_uarttft_read_independently"]["answer"])
        self.assertEqual(len(q["4_file_open_read_order"]["answer"]), 1)
        self.assertEqual(q["5_usb_command_transfer_order"]["answer"]["out_transfers"], 1)
        self.assertEqual(q["7_total_bytes_per_payload"]["answer"]["UartTFT-II_Flash.bin"], 127599044)
        self.assertEqual(q["9_filecrc_flashcrc"]["answer"]["crc_frame_count"], 1)
        self.assertEqual(q["10_final_success_restart"]["answer"]["usb_transfer_count"], 1)

        # Evidence vs inference tags present
        self.assertEqual(q["1_files_opened"]["evidence"]["kind"], "EVIDENCE")
        self.assertEqual(q["5_usb_command_transfer_order"]["evidence"]["kind"], "INFERENCE")

    def test_summary_flags(self):
        tmpdir = tempfile.mkdtemp()
        proc_rows = [
            procmon_row("10:00:01", "updater.exe", "CreateFile", r"C:\pkg\HFD_Code_V2.2.bin"),
            procmon_row("10:00:02", "updater.exe", "ReadFile", r"C:\pkg\HFD_Code_V2.2.bin", detail="305800"),
        ]
        proc_path = write_procmon_csv(tmpdir, proc_rows)
        pcap_path = write_pcapng(tmpdir, [])
        report = mod.build_report(proc_path, pcap_path)
        s = report["summary"]
        self.assertTrue(s["hfd_v22_read"])
        self.assertFalse(s["hfd_v23_read"])
        self.assertFalse(s["uarttft_read"])
        self.assertTrue(s["offline_analyser"])


if __name__ == "__main__":
    unittest.main()
