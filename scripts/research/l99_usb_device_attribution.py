"""AULA L99 Offline USB Device Attribution Utility.

Deterministic offline utility that extracts capture-local USB device
address to VID/PID mappings from existing USB descriptor evidence.

Operates offline only. Verifies capture SHA256 before processing.
Preserves capture-local device addresses. Does not generalize across captures.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator, Optional


EXPECTED_SHA256 = "B4DAD6E13612C615F3A03400BCC9EED8F98F6D02E0B256368B8E82C3C608F5EE"
TARGET_DEVICE_ADDRESSES = {"6", "13", "15", "16"}
DEFAULT_TSHARK_PATH = r"C:\Program Files\Wireshark\tshark.exe"
DEFAULT_CAPTURE_PATH = Path(r"C:\temp\aula-l99-controller\aula_home_numpad_transition.pcapng")


@dataclass(frozen=True, order=True)
class DeviceMapping:
    device_address: str
    vid: str
    pid: str
    vendor_name: str
    product_name: str
    descriptor_frame: int
    descriptor_type: str
    capture_sha256: str

    def to_json(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, order=True)
class AmbiguousMapping:
    device_address: str
    candidates: list[dict]
    capture_sha256: str

    def to_json(self) -> dict:
        return asdict(self)


def verify_capture_sha256(capture_path: Path) -> str:
    """Compute SHA256 of capture file."""
    sha256 = hashlib.sha256()
    with capture_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest().upper()


def run_tshark_extract(capture_path: Path, device_address: str, tshark_path: Optional[str] = None) -> list[dict]:
    """Extract USB device descriptors using tshark."""
    results = []
    filter_expr = f"usb.device_address == {device_address} && usb.bDescriptorType == 0x01"
    effective_tshark = tshark_path if tshark_path else DEFAULT_TSHARK_PATH
    cmd = [
        effective_tshark,
        "-r", str(capture_path),
        "-Y", filter_expr,
        "-T", "fields",
        "-e", "frame.number",
        "-e", "usb.device_address",
        "-e", "usb.idvendor",
        "-e", "usb.idproduct",
        "-e", "usb.bDescriptorType",
        "-e", "usb.capdata"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return results
        for line in proc.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 5:
                results.append({
                    "frame": int(parts[0]),
                    "device_address": parts[1],
                    "idvendor": parts[2].lower() if parts[2] else "",
                    "idproduct": parts[3].lower() if parts[3] else "",
                    "bdescriptortype": parts[4],
                    "capdata": parts[5] if len(parts) > 5 else ""
                })
    except FileNotFoundError:
        raise
    except (subprocess.TimeoutExpired, OSError):
        pass
    return results


def _extract_hex_from_line(line: str) -> Optional[str]:
    """Extract hex value from lines like 'idVendor: Unknown (0xeeef)' or 'idVendor: 0xeeef'."""
    if "(" in line and ")" in line:
        start = line.find("(") + 1
        end = line.find(")")
        val = line[start:end]
        if val.lower().startswith("0x"):
            return val[2:].lower()
    if ":" in line:
        parts = line.split(":", 1)
        if len(parts) > 1:
            val = parts[1].strip()
            if val.lower().startswith("0x"):
                return val[2:].lower()
    return None


def run_tshark_verbose(capture_path: Path, device_address: str, tshark_path: Optional[str] = None) -> list[dict]:
    """Extract detailed USB device descriptor info using tshark -V."""
    results = []
    filter_expr = f"usb.device_address == {device_address} && usb.bDescriptorType == 0x01"
    effective_tshark = tshark_path if tshark_path else DEFAULT_TSHARK_PATH
    cmd = [
        effective_tshark,
        "-r", str(capture_path),
        "-Y", filter_expr,
        "-V"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return results

        current_frame = None
        current_data = {}
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("Frame Number:"):
                if current_frame is not None and current_data:
                    results.append(current_data)
                current_frame = int(line.split(":")[1].strip())
                current_data = {"frame": current_frame, "device_address": device_address}
            elif "idVendor" in line:
                vid = _extract_hex_from_line(line)
                if vid:
                    current_data["idvendor"] = vid
            elif "idProduct" in line:
                pid = _extract_hex_from_line(line)
                if pid:
                    current_data["idproduct"] = pid
            elif "Manufacturer:" in line and "iManufacturer" not in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_data["vendor_name"] = parts[1].strip()
            elif "Product:" in line and "iProduct" not in line:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_data["product_name"] = parts[1].strip()

        if current_frame is not None and current_data:
            results.append(current_data)
    except FileNotFoundError:
        raise
    except (subprocess.TimeoutExpired, OSError):
        pass
    return results


def extract_device_mappings(capture_path: Path, tshark_path: Optional[str] = None) -> tuple[list[DeviceMapping], list[AmbiguousMapping]]:
    """Extract VID/PID mappings for target device addresses."""
    mappings = []
    ambiguous = []

    for dev_addr in sorted(TARGET_DEVICE_ADDRESSES, key=lambda x: int(x)):
        candidates = run_tshark_verbose(capture_path, dev_addr, tshark_path)
        valid_candidates = [c for c in candidates if c.get("idvendor") and c.get("idproduct")]

        if not valid_candidates:
            continue

        if len(valid_candidates) == 1:
            c = valid_candidates[0]
            mappings.append(DeviceMapping(
                device_address=dev_addr,
                vid=c.get("idvendor", "").upper(),
                pid=c.get("idproduct", "").upper(),
                vendor_name=c.get("vendor_name", "Unknown"),
                product_name=c.get("product_name", "Unknown"),
                descriptor_frame=c.get("frame", 0),
                descriptor_type="DEVICE",
                capture_sha256=EXPECTED_SHA256
            ))
        else:
            cand_list = []
            for c in valid_candidates:
                cand_list.append({
                    "frame": c.get("frame", 0),
                    "vid": c.get("idvendor", "").upper(),
                    "pid": c.get("idproduct", "").upper(),
                    "vendor_name": c.get("vendor_name", "Unknown"),
                    "product_name": c.get("product_name", "Unknown")
                })
            ambiguous.append(AmbiguousMapping(
                device_address=dev_addr,
                candidates=cand_list,
                capture_sha256=EXPECTED_SHA256
            ))

    return mappings, ambiguous


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AULA L99 USB Device Attribution Utility")
    parser.add_argument("--capture", type=Path, help="Path to capture file (requires matching SHA256)")
    parser.add_argument("--tshark", type=str, help="Path to tshark executable")
    parser.add_argument("--expected-sha256", type=str, help="Expected SHA256 for explicit capture")
    args = parser.parse_args(argv)

    if args.capture:
        capture_path = args.capture
        if not args.expected_sha256:
            print("Error: --expected-sha256 required when --capture is specified", file=sys.stderr)
            return 1
        expected_sha256 = args.expected_sha256.upper()
    else:
        capture_path = DEFAULT_CAPTURE_PATH
        expected_sha256 = EXPECTED_SHA256

    tshark_path = args.tshark if args.tshark else DEFAULT_TSHARK_PATH

    if not capture_path.exists():
        print(f"Capture not found: {capture_path}", file=sys.stderr)
        return 1

    actual_sha256 = verify_capture_sha256(capture_path)
    if actual_sha256 != expected_sha256:
        print(f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}", file=sys.stderr)
        return 1

    try:
        mappings, ambiguous = extract_device_mappings(capture_path, tshark_path)
    except FileNotFoundError:
        print(f"tshark not found: {tshark_path}", file=sys.stderr)
        return 2

    output = {
        "capture": capture_path.name,
        "capture_sha256": expected_sha256,
        "device_mappings": [m.to_json() for m in mappings],
        "ambiguous_mappings": [a.to_json() for a in ambiguous],
        "target_devices": sorted(TARGET_DEVICE_ADDRESSES, key=lambda x: int(x)),
        "mapped_devices": sorted([m.device_address for m in mappings], key=lambda x: int(x)),
        "unmapped_devices": sorted(list(TARGET_DEVICE_ADDRESSES - {m.device_address for m in mappings}), key=lambda x: int(x))
    }

    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())