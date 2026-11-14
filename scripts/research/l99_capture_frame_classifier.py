"""AULA L99 Offline USB Runtime Frame Classifier.

Deterministic offline classifier for existing AULA L99 USB capture payloads.
Uses existing CSV exports only. No hardware access. Bounded memory.
"""

import csv
import struct
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional


MAGIC = b'\x5a\xa5'
OPCODE_READ = 0x03
OPCODE_WRITE = 0x10

MIN_BODY_LENGTH = 3
MAX_BODY_LENGTH = 253
MAX_READ_WORD_COUNT = 8
ADDRESS_MIN = 0x0000
ADDRESS_MAX = 0xFFFF

LARGE_PAYLOAD_THRESHOLD = 1000
MAX_SHORT_RUNTIME_FRAME = 258

HID_MOUSE_REPORT_ID = 0x01
HID_KEYBOARD_REPORT_ID = 0x02
HID_CONSUMER_REPORT_ID = 0x03

NUMPAD_TRANSITION_DEVICE_MAP = {
    "6": ("05E3", "0626"),
    "13": ("1A86", "8091"),
    "15": ("EEEF", "268A"),
    "16": ("0C45", "800A"),
}

SCREEN_DEVICE_VIDPID = {
    ("EEEF", "268A"),
    ("0C45", "800A"),
}

NON_SCREEN_DEVICE_VIDPID = {
    ("05E3", "0626"),
    ("1A86", "8091"),
}


class FrameClass(Enum):
    VALID_RUNTIME = "valid_runtime"
    INVALID_RUNTIME = "invalid_runtime"
    UNVERIFIED_LARGE_PAYLOAD = "unverified_large_payload"
    UNKNOWN = "unknown"
    CRC_VALID_UNSUPPORTED_OPCODE = "crc_valid_unsupported_opcode"


class EndpointAttribution(Enum):
    VERIFIED_SCREEN = "verified_screen"
    VERIFIED_NON_SCREEN = "verified_non_screen"
    UNVERIFIED = "unverified"


class DecodeError(Enum):
    TRUNCATED = "truncated"
    INVALID_MAGIC = "invalid_magic"
    INVALID_LENGTH = "invalid_length"
    INVALID_CRC = "invalid_crc"
    UNSUPPORTED_OPCODE = "unsupported_opcode"
    INVALID_ADDRESS = "invalid_address"
    INVALID_WORD_COUNT = "invalid_word_count"
    EMPTY_WRITE_PAYLOAD = "empty_write_payload"
    EXTRA_TRAILING_BYTES = "extra_trailing_bytes"
    BODY_TOO_SHORT = "body_too_short"
    PAYLOAD_NOT_EVEN = "payload_not_even"


def get_device_mapping(capture_name: str) -> dict[str, tuple[str, str]]:
    if capture_name == "aula_home_numpad_transition":
        return NUMPAD_TRANSITION_DEVICE_MAP
    return {}


def get_endpoint_attribution(capture_name: str, device: str, endpoint: str) -> EndpointAttribution:
    device_map = get_device_mapping(capture_name)
    if device in device_map:
        vid, pid = device_map[device]
        if (vid, pid) in SCREEN_DEVICE_VIDPID:
            return EndpointAttribution.VERIFIED_SCREEN
        if (vid, pid) in NON_SCREEN_DEVICE_VIDPID:
            return EndpointAttribution.VERIFIED_NON_SCREEN
    return EndpointAttribution.UNVERIFIED


@dataclass(frozen=True, order=True)
class FrameCandidate:
    capture_file: str
    frame_number: int
    timestamp: str
    device: str
    endpoint: str
    direction: str
    frame_class: FrameClass
    endpoint_attribution: EndpointAttribution
    decode_error: Optional[DecodeError] = None
    opcode: Optional[int] = None
    word_address: Optional[int] = None
    word_count: Optional[int] = None
    write_words: Optional[tuple] = None
    payload_hex: str = ""
    payload_length: int = 0


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc & 0xFFFF


def parse_endpoint_direction(endpoint: str) -> str:
    try:
        ep_addr = int(endpoint, 16) if endpoint.startswith("0x") else int(endpoint)
        if ep_addr & 0x80:
            return "IN"
        return "OUT"
    except (ValueError, AttributeError):
        return "UNKNOWN"


def is_hid_report(payload: bytes) -> bool:
    if len(payload) < 1:
        return False
    report_id = payload[0]
    if report_id in (HID_MOUSE_REPORT_ID, HID_KEYBOARD_REPORT_ID, HID_CONSUMER_REPORT_ID):
        if len(payload) >= 2:
            return True
    return False


def decode_runtime_frame(payload: bytes) -> tuple[bytes, Optional[DecodeError]]:
    if len(payload) < 4:
        return b"", DecodeError.TRUNCATED

    if payload[:2] != MAGIC:
        return b"", DecodeError.INVALID_MAGIC

    declared_length = payload[2]
    expected_total = declared_length + 3

    if len(payload) < expected_total:
        return b"", DecodeError.TRUNCATED

    if len(payload) > expected_total:
        return b"", DecodeError.EXTRA_TRAILING_BYTES

    body = payload[3:-2]
    received_crc = struct.unpack('<H', payload[-2:])[0]
    computed_crc = crc16_modbus(body)

    if received_crc != computed_crc:
        return b"", DecodeError.INVALID_CRC

    return body, None


def classify_body(body: bytes) -> tuple[FrameClass, Optional[DecodeError], Optional[int], Optional[int], Optional[int], Optional[tuple]]:
    if len(body) < 1:
        return FrameClass.INVALID_RUNTIME, DecodeError.BODY_TOO_SHORT, None, None, None, None

    opcode = body[0]

    if opcode == OPCODE_READ:
        if len(body) != 5:
            return FrameClass.INVALID_RUNTIME, DecodeError.INVALID_WORD_COUNT, None, None, None, None
        word_address = struct.unpack('>H', body[1:3])[0]
        word_count = struct.unpack('>H', body[3:5])[0]
        if not (1 <= word_count <= MAX_READ_WORD_COUNT):
            return FrameClass.INVALID_RUNTIME, DecodeError.INVALID_WORD_COUNT, None, None, None, None
        return FrameClass.VALID_RUNTIME, None, opcode, word_address, word_count, None

    if opcode == OPCODE_WRITE:
        if len(body) < 4:
            return FrameClass.INVALID_RUNTIME, DecodeError.EMPTY_WRITE_PAYLOAD, None, None, None, None
        if (len(body) - 3) % 2 != 0:
            return FrameClass.INVALID_RUNTIME, DecodeError.PAYLOAD_NOT_EVEN, None, None, None, None
        word_address = struct.unpack('>H', body[1:3])[0]
        words = []
        for i in range(3, len(body), 2):
            words.append(struct.unpack('>H', body[i:i+2])[0])
        return FrameClass.VALID_RUNTIME, None, opcode, word_address, None, tuple(words)

    return FrameClass.INVALID_RUNTIME, DecodeError.UNSUPPORTED_OPCODE, opcode, None, None, None


def classify_crc_valid_unsupported_opcode(body: bytes) -> tuple[FrameClass, Optional[DecodeError], Optional[int], Optional[int], Optional[int], Optional[tuple]]:
    """Classify a CRC-valid frame with an unsupported opcode.
    
    Returns CRC_VALID_UNSUPPORTED_OPCODE for frames that have valid CRC but unsupported opcode.
    """
    if len(body) < 1:
        return FrameClass.INVALID_RUNTIME, DecodeError.BODY_TOO_SHORT, None, None, None, None

    opcode = body[0]

    if opcode == OPCODE_READ or opcode == OPCODE_WRITE:
        # Should not happen - these are handled by classify_body
        return classify_body(body)

    return FrameClass.CRC_VALID_UNSUPPORTED_OPCODE, DecodeError.UNSUPPORTED_OPCODE, opcode, None, None, None


def classify_payload(payload_hex: str) -> tuple[FrameClass, Optional[DecodeError], Optional[int], Optional[int], Optional[int], Optional[tuple]]:
    try:
        payload = bytes.fromhex(payload_hex)
    except ValueError:
        return FrameClass.UNKNOWN, None, None, None, None, None

    if len(payload) < 4:
        return FrameClass.UNKNOWN, None, None, None, None, None

    if is_hid_report(payload):
        return FrameClass.UNKNOWN, None, None, None, None, None

    if len(payload) >= LARGE_PAYLOAD_THRESHOLD:
        if payload[:2] == MAGIC:
            body, error = decode_runtime_frame(payload)
            if error is None:
                frame_class, error, opcode, word_addr, word_count, words = classify_body(body)
                if frame_class == FrameClass.VALID_RUNTIME:
                    return frame_class, error, opcode, word_addr, word_count, words
                if frame_class == FrameClass.INVALID_RUNTIME and error == DecodeError.UNSUPPORTED_OPCODE:
                    return FrameClass.CRC_VALID_UNSUPPORTED_OPCODE, error, opcode, word_addr, word_count, words
        return FrameClass.UNVERIFIED_LARGE_PAYLOAD, None, None, None, None, None

    if payload[:2] != MAGIC:
        return FrameClass.UNKNOWN, None, None, None, None, None

    body, error = decode_runtime_frame(payload)
    if error:
        return FrameClass.INVALID_RUNTIME, error, None, None, None, None

    frame_class, error, opcode, word_addr, word_count, words = classify_body(body)
    if frame_class == FrameClass.VALID_RUNTIME:
        return frame_class, error, opcode, word_addr, word_count, words

    if frame_class == FrameClass.INVALID_RUNTIME and error == DecodeError.UNSUPPORTED_OPCODE:
        return FrameClass.CRC_VALID_UNSUPPORTED_OPCODE, error, opcode, word_addr, word_count, words

    return FrameClass.INVALID_RUNTIME, error, opcode, word_addr, word_count, words


def iterate_csv_rows(csv_path: Path) -> Iterator[dict]:
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def extract_short_runtime_frames(payload: bytes, max_frame_len: int = MAX_SHORT_RUNTIME_FRAME) -> list[tuple[bytes, int, int]]:
    """Extract valid short runtime frames from a payload.
    
    Returns list of (frame_bytes, start_offset, frame_length) for each valid frame found.
    Frames are validated independently: magic, length, opcode, CRC16.
    """
    frames = []
    offset = 0
    payload_len = len(payload)
    
    while offset + 4 <= payload_len and offset <= max_frame_len:
        remaining = payload_len - offset
        if remaining < 4:
            break
            
        if payload[offset:offset+2] != MAGIC:
            break
            
        declared_length = payload[offset + 2]
        expected_total = declared_length + 3
        
        if expected_total > max_frame_len:
            break
            
        if remaining < expected_total:
            break
            
        frame_bytes = payload[offset:offset + expected_total]
        body = frame_bytes[3:-2]
        received_crc = struct.unpack('<H', frame_bytes[-2:])[0]
        computed_crc = crc16_modbus(body)
        
        if received_crc != computed_crc:
            break
            
        if len(body) < 1:
            break
            
        opcode = body[0]
        if opcode not in (OPCODE_READ, OPCODE_WRITE):
            break
            
        if opcode == OPCODE_READ and len(body) != 5:
            break
        if opcode == OPCODE_WRITE and len(body) < 4:
            break
        if opcode == OPCODE_WRITE and (len(body) - 3) % 2 != 0:
            break
            
        frames.append((frame_bytes, offset, expected_total))
        offset += expected_total
        
    return frames


def extract_crc_valid_frames(payload: bytes, max_frame_len: int = MAX_SHORT_RUNTIME_FRAME) -> list[tuple[bytes, int, int]]:
    """Extract all CRC-valid short frames from a payload, including unsupported opcodes.
    
    Returns list of (frame_bytes, start_offset, frame_length) for each frame with valid CRC.
    Frames are validated independently: magic, length, CRC16. Opcode is not validated here.
    """
    frames = []
    offset = 0
    payload_len = len(payload)
    
    while offset + 4 <= payload_len and offset <= max_frame_len:
        remaining = payload_len - offset
        if remaining < 4:
            break
            
        if payload[offset:offset+2] != MAGIC:
            break
            
        declared_length = payload[offset + 2]
        expected_total = declared_length + 3
        
        if expected_total > max_frame_len:
            break
            
        if remaining < expected_total:
            break
            
        frame_bytes = payload[offset:offset + expected_total]
        body = frame_bytes[3:-2]
        received_crc = struct.unpack('<H', frame_bytes[-2:])[0]
        computed_crc = crc16_modbus(body)
        
        if received_crc != computed_crc:
            break
            
        if len(body) < 1:
            break
            
        frames.append((frame_bytes, offset, expected_total))
        offset += expected_total
        
    return frames


def process_capture(capture_dir: Path) -> Iterator[FrameCandidate]:
    payloads_csv = capture_dir / "all_payloads.csv"
    if not payloads_csv.exists():
        return

    capture_name = capture_dir.name

    for row in iterate_csv_rows(payloads_csv):
        try:
            frame_num = int(row.get("frame", 0))
        except ValueError:
            continue

        timestamp = row.get("time", "")
        device = row.get("device", "")
        endpoint = row.get("endpoint", "")
        payload_hex = row.get("payload", "")
        try:
            data_len = int(row.get("data_len", 0))
        except ValueError:
            data_len = 0

        direction = parse_endpoint_direction(endpoint)

        if not payload_hex:
            candidate = FrameCandidate(
                capture_file=capture_name,
                frame_number=frame_num,
                timestamp=timestamp,
                device=device,
                endpoint=endpoint,
                direction=direction,
                frame_class=FrameClass.UNKNOWN,
                endpoint_attribution=EndpointAttribution.UNVERIFIED,
                payload_hex="",
                payload_length=0,
            )
            yield candidate
            continue

        payload = bytes.fromhex(payload_hex)
        crc_valid_frames = extract_crc_valid_frames(payload)
        
        if len(crc_valid_frames) > 1:
            for idx, (frame_bytes, start_offset, frame_len) in enumerate(crc_valid_frames):
                frame_class, error, opcode, word_addr, word_count, words = classify_payload(frame_bytes.hex())
                endpoint_attribution = get_endpoint_attribution(capture_name, device, endpoint)
                
                candidate = FrameCandidate(
                    capture_file=capture_name,
                    frame_number=frame_num,
                    timestamp=timestamp,
                    device=device,
                    endpoint=endpoint,
                    direction=direction,
                    frame_class=frame_class,
                    endpoint_attribution=endpoint_attribution,
                    decode_error=error,
                    opcode=opcode,
                    word_address=word_addr,
                    word_count=word_count if opcode == OPCODE_READ else None,
                    write_words=words if opcode == OPCODE_WRITE else None,
                    payload_hex=frame_bytes.hex(),
                    payload_length=frame_len,
                )
                yield candidate
            
            trailing_bytes = payload[crc_valid_frames[-1][1] + crc_valid_frames[-1][2]:]
            if trailing_bytes:
                candidate = FrameCandidate(
                    capture_file=capture_name,
                    frame_number=frame_num,
                    timestamp=timestamp,
                    device=device,
                    endpoint=endpoint,
                    direction=direction,
                    frame_class=FrameClass.UNKNOWN,
                    endpoint_attribution=EndpointAttribution.UNVERIFIED,
                    decode_error=DecodeError.EXTRA_TRAILING_BYTES,
                    payload_hex=trailing_bytes.hex(),
                    payload_length=len(trailing_bytes),
                )
                yield candidate
        elif len(crc_valid_frames) == 1:
            frame_bytes, start_offset, frame_len = crc_valid_frames[0]
            frame_class, error, opcode, word_addr, word_count, words = classify_payload(frame_bytes.hex())
            endpoint_attribution = get_endpoint_attribution(capture_name, device, endpoint)
            
            candidate = FrameCandidate(
                capture_file=capture_name,
                frame_number=frame_num,
                timestamp=timestamp,
                device=device,
                endpoint=endpoint,
                direction=direction,
                frame_class=frame_class,
                endpoint_attribution=endpoint_attribution,
                decode_error=error,
                opcode=opcode,
                word_address=word_addr,
                word_count=word_count if opcode == OPCODE_READ else None,
                write_words=words if opcode == OPCODE_WRITE else None,
                payload_hex=frame_bytes.hex(),
                payload_length=frame_len,
            )
            yield candidate
            
            trailing_bytes = payload[frame_len:]
            if trailing_bytes:
                candidate = FrameCandidate(
                    capture_file=capture_name,
                    frame_number=frame_num,
                    timestamp=timestamp,
                    device=device,
                    endpoint=endpoint,
                    direction=direction,
                    frame_class=FrameClass.UNKNOWN,
                    endpoint_attribution=EndpointAttribution.UNVERIFIED,
                    decode_error=DecodeError.EXTRA_TRAILING_BYTES,
                    payload_hex=trailing_bytes.hex(),
                    payload_length=len(trailing_bytes),
                )
                yield candidate
        else:
            frame_class, error, opcode, word_addr, word_count, words = classify_payload(payload_hex)
            endpoint_attribution = get_endpoint_attribution(capture_name, device, endpoint)
            
            candidate = FrameCandidate(
                capture_file=capture_name,
                frame_number=frame_num,
                timestamp=timestamp,
                device=device,
                endpoint=endpoint,
                direction=direction,
                frame_class=frame_class,
                endpoint_attribution=endpoint_attribution,
                decode_error=error,
                opcode=opcode,
                word_address=word_addr,
                word_count=word_count if opcode == OPCODE_READ else None,
                write_words=words if opcode == OPCODE_WRITE else None,
                payload_hex=payload_hex,
                payload_length=data_len,
            )
            yield candidate


def classify_all_captures(analysis_root: Path) -> list[FrameCandidate]:
    candidates = []
    if not analysis_root.exists():
        return candidates

    for capture_dir in sorted(analysis_root.iterdir()):
        if not capture_dir.is_dir():
            continue
        candidates.extend(process_capture(capture_dir))

    candidates.sort()
    return candidates


def print_candidates(candidates: list[FrameCandidate], limit: int = 0) -> None:
    print(f"{'Capture':<30} {'Frame':>8} {'Dir':<5} {'Class':<25} {'Attrib':<18} {'Error':<20} {'Opcode':>6} {'Addr':>6} {'Count':>6} {'Words'}")
    print("-" * 160)
    count = 0
    for c in candidates:
        if limit and count >= limit:
            break
        error_str = c.decode_error.value if c.decode_error else ""
        attrib_str = c.endpoint_attribution.value
        opcode_str = f"0x{c.opcode:02X}" if c.opcode is not None else ""
        addr_str = f"0x{c.word_address:04X}" if c.word_address is not None else ""
        count_str = str(c.word_count) if c.word_count is not None else ""
        words_str = " ".join(f"0x{w:04X}" for w in c.write_words) if c.write_words else ""
        print(f"{c.capture_file:<30} {c.frame_number:>8} {c.direction:<5} {c.frame_class.value:<25} {attrib_str:<18} {error_str:<20} {opcode_str:>6} {addr_str:>6} {count_str:>6} {words_str}")
        count += 1


def print_summary(candidates: list[FrameCandidate]) -> None:
    total = len(candidates)
    valid = [c for c in candidates if c.frame_class == FrameClass.VALID_RUNTIME]
    invalid = [c for c in candidates if c.frame_class == FrameClass.INVALID_RUNTIME]
    large = [c for c in candidates if c.frame_class == FrameClass.UNVERIFIED_LARGE_PAYLOAD]
    unknown = [c for c in candidates if c.frame_class == FrameClass.UNKNOWN]

    print(f"Total candidates classified: {total}")
    print()
    print(f"Valid runtime frames:         {len(valid)}")
    print(f"Invalid runtime frames:       {len(invalid)}")
    print(f"Unverified large payload:     {len(large)}")
    print(f"Unknown payload:              {len(unknown)}")
    print()

    verified_screen = [c for c in candidates if c.endpoint_attribution == EndpointAttribution.VERIFIED_SCREEN]
    verified_non_screen = [c for c in candidates if c.endpoint_attribution == EndpointAttribution.VERIFIED_NON_SCREEN]
    unverified = [c for c in candidates if c.endpoint_attribution == EndpointAttribution.UNVERIFIED]
    print(f"Verified screen endpoints:    {len(verified_screen)}")
    print(f"Verified non-screen endpoints:{len(verified_non_screen)}")
    print(f"Unverified endpoints:         {len(unverified)}")
    print()


def print_device_endpoint_breakdown(candidates: list[FrameCandidate]) -> None:
    from collections import defaultdict

    device_endpoint_counts = defaultdict(lambda: defaultdict(int))

    for c in candidates:
        key = (c.capture_file, c.device, c.endpoint)
        device_endpoint_counts[key][c.frame_class.value] += 1

    print("=== Per-Capture Per-Device Per-Endpoint Breakdown ===")
    for (capture, device, endpoint), counts in sorted(device_endpoint_counts.items()):
        total = sum(counts.values())
        print(f"  Capture: {capture} | Device: {device} | Endpoint: {endpoint} | Total: {total}")
        for frame_class, count in sorted(counts.items()):
            print(f"    {frame_class}: {count}")
    print()


def print_unverified_device_mappings(candidates: list[FrameCandidate]) -> None:
    unverified_devices = set()
    for c in candidates:
        if c.endpoint_attribution == EndpointAttribution.UNVERIFIED:
            unverified_devices.add((c.capture_file, c.device, c.endpoint))

    print("=== Unverified Device Mappings ===")
    for capture, device, endpoint in sorted(unverified_devices):
        print(f"  Capture: {capture} | Device: {device} | Endpoint: {endpoint}")
    print()


def main() -> int:
    analysis_root = Path(__file__).resolve().parent.parent.parent / "capture_analysis"
    candidates = classify_all_captures(analysis_root)

    print_summary(candidates)

    print("=== Valid Runtime Frames ===")
    valid = [c for c in candidates if c.frame_class == FrameClass.VALID_RUNTIME]
    for c in valid:
        words_str = " ".join(f"0x{w:04X}" for w in c.write_words) if c.write_words else ""
        count_str = str(c.word_count) if c.word_count is not None else ""
        print(f"  {c.capture_file} frame={c.frame_number} time={c.timestamp} "
              f"dev={c.device} ep={c.endpoint} dir={c.direction} "
              f"opcode=0x{c.opcode:02X} addr=0x{c.word_address:04X} count={count_str} words=[{words_str}]")

    if valid:
        print()
        print("=== Invalid Runtime Frames (errors) ===")
        invalid = [c for c in candidates if c.frame_class == FrameClass.INVALID_RUNTIME]
        for c in invalid[:20]:
            print(f"  {c.capture_file} frame={c.frame_number} dev={c.device} ep={c.endpoint} error={c.decode_error.value if c.decode_error else 'unknown'}")

    print()
    print_device_endpoint_breakdown(candidates)
    print_unverified_device_mappings(candidates)

    return 0


if __name__ == "__main__":
    sys.exit(main())