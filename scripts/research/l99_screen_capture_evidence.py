"""AULA L99 Offline Screen Capture Evidence Report.

Deterministic offline utility summarizing existing USB capture evidence
without guessing screen-device identity.

Uses existing CSV exports only. No hardware access. Bounded memory.
Standard library only.
"""

import csv
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True, order=True)
class DeviceEndpointKey:
    capture_name: str
    device: str
    endpoint: str


@dataclass
class DeviceEndpointStats:
    direction: str
    payload_sizes: list[int] = field(default_factory=list)
    transfer_count: int = 0
    has_payload_data: bool = False


@dataclass(frozen=True, order=True)
class AttributionLabel:
    VERIFIED_SCREEN = "verified_screen"
    VERIFIED_NON_SCREEN = "verified_non_screen"
    UNVERIFIED = "unverified"


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with filepath.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_endpoint_direction(endpoint: str) -> str:
    try:
        ep_addr = int(endpoint, 16) if endpoint.startswith("0x") else int(endpoint)
        if ep_addr & 0x80:
            return "IN"
        return "OUT"
    except (ValueError, AttributeError):
        return "UNKNOWN"


def load_device_mapping(mapping_path: Path) -> dict[str, tuple[str, str]]:
    """Load capture-local VID/PID mapping from CSV.
    
    Expected columns: capture_name, device, vid, pid
    """
    mapping = {}
    if not mapping_path.exists():
        return mapping
    with mapping_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            capture = row.get('capture_name', '').strip()
            device = row.get('device', '').strip()
            vid = row.get('vid', '').strip()
            pid = row.get('pid', '').strip()
            if capture and device and vid and pid:
                mapping[(capture, device)] = (vid.upper(), pid.upper())
    return mapping


def load_verified_vidpid(verified_path: Path) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Load verified screen and non-screen VID/PID pairs from CSV.
    
    Expected columns: vid, pid, role
    """
    screen_vidpid = set()
    non_screen_vidpid = set()
    if not verified_path.exists():
        return screen_vidpid, non_screen_vidpid
    with verified_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = row.get('vid', '').strip().upper()
            pid = row.get('pid', '').strip().upper()
            role = row.get('role', '').strip().lower()
            if vid and pid:
                if role == 'screen':
                    screen_vidpid.add((vid, pid))
                elif role in ('non_screen', 'keyboard', 'touch', 'pointer'):
                    non_screen_vidpid.add((vid, pid))
    return screen_vidpid, non_screen_vidpid


def get_endpoint_provenance(
    capture_name: str,
    device: str,
    device_mapping: dict,
    screen_vidpid: set,
    non_screen_vidpid: set
) -> dict:
    key = (capture_name, device)
    if key in device_mapping:
        vid, pid = device_mapping[key]
        if (vid, pid) in screen_vidpid:
            return {
                "vid": vid,
                "pid": pid,
                "mapping_source": "csv_assertion",
                "vidpid_verified": True,
                "attribution_basis": "csv_assertion",
                "attribution": AttributionLabel.VERIFIED_SCREEN
            }
        if (vid, pid) in non_screen_vidpid:
            return {
                "vid": vid,
                "pid": pid,
                "mapping_source": "csv_assertion",
                "vidpid_verified": True,
                "attribution_basis": "csv_assertion",
                "attribution": AttributionLabel.VERIFIED_NON_SCREEN
            }
        return {
            "vid": vid,
            "pid": pid,
            "mapping_source": "csv_assertion",
            "vidpid_verified": False,
            "attribution_basis": "csv_assertion",
            "attribution": AttributionLabel.UNVERIFIED
        }
    return {
        "vid": "",
        "pid": "",
        "mapping_source": "none",
        "vidpid_verified": False,
        "attribution_basis": "none",
        "attribution": AttributionLabel.UNVERIFIED
    }


def iterate_csv_rows(csv_path: Path) -> Iterator[dict]:
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def process_capture(
    capture_dir: Path,
    device_mapping: dict,
    screen_vidpid: set,
    non_screen_vidpid: set
) -> dict:
    payloads_csv = capture_dir / "all_payloads.csv"
    if not payloads_csv.exists():
        return {}

    capture_name = capture_dir.name
    csv_sha256 = compute_sha256(payloads_csv)

    stats_by_key: dict[DeviceEndpointKey, DeviceEndpointStats] = defaultdict(
        lambda: DeviceEndpointStats(direction="UNKNOWN")
    )

    for row in iterate_csv_rows(payloads_csv):
        try:
            device = row.get("device", "").strip()
            endpoint = row.get("endpoint", "").strip()
            data_len_str = row.get("data_len", "0").strip()
            payload_hex = row.get("payload", "").strip()
        except Exception:
            continue

        if not device or not endpoint:
            continue

        key = DeviceEndpointKey(
            capture_name=capture_name,
            device=device,
            endpoint=endpoint
        )

        stats = stats_by_key[key]
        stats.direction = parse_endpoint_direction(endpoint)

        try:
            data_len = int(data_len_str)
        except ValueError:
            data_len = 0

        if data_len > 0:
            stats.payload_sizes.append(data_len)
            stats.transfer_count += 1

        if payload_hex:
            stats.has_payload_data = True

    result = {}
    for key, stats in sorted(stats_by_key.items()):
        provenance = get_endpoint_provenance(
            key.capture_name, key.device, device_mapping, screen_vidpid, non_screen_vidpid
        )

        payload_sizes = sorted(stats.payload_sizes)
        size_dist = {}
        for sz in payload_sizes:
            size_dist[str(sz)] = size_dist.get(str(sz), 0) + 1

        result[key] = {
            "capture_name": key.capture_name,
            "source_csv_sha256": csv_sha256,
            "device": key.device,
            "endpoint": key.endpoint,
            "direction": stats.direction,
            "attribution": provenance["attribution"],
            "vid": provenance["vid"],
            "pid": provenance["pid"],
            "mapping_source": provenance["mapping_source"],
            "vidpid_verified": provenance["vidpid_verified"],
            "attribution_basis": provenance["attribution_basis"],
            "payload_size_distribution": size_dist,
            "transfer_count": stats.transfer_count,
            "has_payload_data": stats.has_payload_data,
        }

    return result


def process_all_captures(
    analysis_root: Path,
    device_mapping: dict,
    screen_vidpid: set,
    non_screen_vidpid: set
) -> list[dict]:
    all_results = []
    if not analysis_root.exists():
        return all_results

    for capture_dir in sorted(analysis_root.iterdir()):
        if not capture_dir.is_dir():
            continue
        capture_results = process_capture(
            capture_dir, device_mapping, screen_vidpid, non_screen_vidpid
        )
        for entry in sorted(capture_results.values(), key=lambda x: (x["device"], x["endpoint"])):
            all_results.append(entry)

    return all_results


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python l99_screen_capture_evidence.py <capture_analysis_root> [device_mapping.csv] [verified_vidpid.csv]", file=sys.stderr)
        return 1

    analysis_root = Path(sys.argv[1]).resolve()
    device_mapping_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path("device_mapping.csv")
    verified_vidpid_path = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else Path("verified_vidpid.csv")

    device_mapping = load_device_mapping(device_mapping_path)
    screen_vidpid, non_screen_vidpid = load_verified_vidpid(verified_vidpid_path)

    device_mapping_sha256 = compute_sha256(device_mapping_path) if device_mapping_path.exists() else ""
    verified_vidpid_sha256 = compute_sha256(verified_vidpid_path) if verified_vidpid_path.exists() else ""

    results = process_all_captures(
        analysis_root, device_mapping, screen_vidpid, non_screen_vidpid
    )

    output = {
        "capture_evidence": results,
        "metadata": {
            "analysis_root": str(analysis_root),
            "device_mapping_source": str(device_mapping_path),
            "verified_vidpid_source": str(verified_vidpid_path),
            "device_mapping_sha256": device_mapping_sha256,
            "verified_vidpid_sha256": verified_vidpid_sha256,
            "total_entries": len(results),
        }
    }

    json.dump(output, sys.stdout, separators=(',', ':'), ensure_ascii=False)
    sys.stdout.write('\n')
    return 0


if __name__ == "__main__":
    sys.exit(main())