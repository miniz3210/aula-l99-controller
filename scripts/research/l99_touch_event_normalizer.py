#!/usr/bin/env python3
"""
AULA L99 Offline Touch Event Normalizer

Normalizes existing capture evidence (touch_reports.csv, keyboard_reports.csv)
into deterministic JSON output. Streaming CSV processing, no live hardware access.
"""

import csv
import json
import sys
import hashlib
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List


TOUCH_STATE_MAP = {
    '1': 'press',
    '0': 'release',
}


def compute_source_hash(row: Dict[str, str]) -> str:
    """Compute deterministic hash of raw source row for traceability."""
    raw = ','.join(str(row.get(k, '')) for k in sorted(row.keys()))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def normalize_touch_event(row: Dict[str, str], capture_name: str) -> Dict[str, Any]:
    """Normalize a single touch report row."""
    state_byte = row.get('state_byte', '').strip()
    event_type = 'touch'
    press_release = TOUCH_STATE_MAP.get(state_byte, 'unknown')

    return {
        'source_capture': capture_name,
        'usb_frame_number': safe_int(row.get('frame', 0)),
        'timestamp': safe_float(row.get('time', 0.0)),
        'device_identity': {
            'capture_local_device_id': row.get('device', ''),
            'endpoint': row.get('endpoint', ''),
        },
        'event_type': event_type,
        'press_release_state': press_release,
        'known_return_code': state_byte if state_byte else None,
        'raw_source': {
            'frame': row.get('frame', ''),
            'time': row.get('time', ''),
            'device': row.get('device', ''),
            'endpoint': row.get('endpoint', ''),
            'prefix': row.get('prefix', ''),
            'state_byte': state_byte,
            'payload': row.get('payload', ''),
        },
        'source_hash': compute_source_hash(row),
    }


def normalize_keyboard_event(row: Dict[str, str], capture_name: str) -> Dict[str, Any]:
    """Normalize a single keyboard report row."""
    state = row.get('state', '').strip().lower()
    press_release = state if state in ('press', 'release') else 'unknown'

    modifier = row.get('modifier', '').strip()
    usage_id = row.get('usage_ids', '').strip()
    key_name = row.get('names', '').strip()
    
    def is_meaningful(v: str) -> bool:
        v = v.strip().lower()
        return v and v not in ('0x00', '0', '')

    has_key_info = any(is_meaningful(v) for v in (modifier, usage_id, key_name))

    return {
        'source_capture': capture_name,
        'usb_frame_number': safe_int(row.get('frame', 0)),
        'timestamp': safe_float(row.get('time', 0.0)),
        'device_identity': {
            'capture_local_device_id': row.get('device', ''),
            'endpoint': row.get('endpoint', ''),
        },
        'event_type': 'keyboard_hid',
        'press_release_state': press_release,
        'known_return_code': {
            'modifier': modifier,
            'usage_id': usage_id,
            'key_name': key_name,
        } if has_key_info else None,
        'raw_source': {
            'frame': row.get('frame', ''),
            'time': row.get('time', ''),
            'device': row.get('device', ''),
            'endpoint': row.get('endpoint', ''),
            'state': row.get('state', ''),
            'modifier': row.get('modifier', ''),
            'usage_ids': row.get('usage_ids', ''),
            'names': row.get('names', ''),
            'payload': row.get('payload', ''),
        },
        'source_hash': compute_source_hash(row),
    }


def normalize_unknown_event(row: Dict[str, str], capture_name: str, csv_type: str) -> Dict[str, Any]:
    """Normalize an unknown/unsupported report row."""
    return {
        'source_capture': capture_name,
        'usb_frame_number': safe_int(row.get('frame', 0)),
        'timestamp': safe_float(row.get('time', 0.0)),
        'device_identity': {
            'capture_local_device_id': row.get('device', ''),
            'endpoint': row.get('endpoint', ''),
        },
        'event_type': 'unknown',
        'press_release_state': 'unknown',
        'known_return_code': None,
        'raw_source': dict(row),
        'source_hash': compute_source_hash(row),
    }


def process_touch_csv(filepath: Path, capture_name: str) -> Iterator[Dict[str, Any]]:
    """Stream process touch_reports.csv"""
    with filepath.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            frame_val = row.get('frame', '').strip()
            if not frame_val:
                continue
            try:
                int(frame_val)
            except ValueError:
                continue
            yield normalize_touch_event(row, capture_name)


def process_keyboard_csv(filepath: Path, capture_name: str) -> Iterator[Dict[str, Any]]:
    """Stream process keyboard_reports.csv"""
    with filepath.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('frame'):
                continue
            yield normalize_keyboard_event(row, capture_name)


def normalize_capture(capture_dir: Path) -> List[Dict[str, Any]]:
    """Normalize all events in a capture directory."""
    events = []
    capture_name = capture_dir.name

    touch_file = capture_dir / 'touch_reports.csv'
    if touch_file.exists():
        for event in process_touch_csv(touch_file, capture_name):
            events.append(event)

    keyboard_file = capture_dir / 'keyboard_reports.csv'
    if keyboard_file.exists():
        for event in process_keyboard_csv(keyboard_file, capture_name):
            events.append(event)

    events.sort(key=lambda e: (e['usb_frame_number'], e['timestamp']))
    return events


def main():
    if len(sys.argv) < 2:
        print("Usage: l99_touch_event_normalizer.py <capture_dir> [output.json]", file=sys.stderr)
        sys.exit(1)

    capture_dir = Path(sys.argv[1])
    if not capture_dir.exists() or not capture_dir.is_dir():
        print(f"Error: {capture_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    events = normalize_capture(capture_dir)

    output = {
        'capture': capture_dir.name,
        'event_count': len(events),
        'events': events,
    }

    json_output = json.dumps(output, separators=(',', ':'), ensure_ascii=False)

    if len(sys.argv) >= 3:
        Path(sys.argv[2]).write_text(json_output)
    else:
        print(json_output)


if __name__ == '__main__':
    main()