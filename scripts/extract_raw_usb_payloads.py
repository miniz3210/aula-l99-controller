import json
import subprocess
from pathlib import Path


TSHARK = Path(
    r"C:\Program Files\Wireshark\tshark.exe"
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CAPTURE_FILE = (
    PROJECT_ROOT / "aula_solid_white.pcapng"
)

OUTPUT_FILE = (
    PROJECT_ROOT / "solid_white_payload_hex.txt"
)

DISPLAY_FILTER = (
    "usb.device_address == 15 "
    "&& usb.endpoint_address == 0x03 "
    "&& frame.len == 2087"
)

USBPCAP_HEADER_SIZE = 27
EXPECTED_FRAME_SIZE = 2087
EXPECTED_PAYLOAD_SIZE = 2060
EXPECTED_DATA_SIZE = 2048
EXPECTED_PACKET_COUNT = 150



def run_tshark():
    command = [
        str(TSHARK),
        "-r",
        str(CAPTURE_FILE),
        "-Y",
        DISPLAY_FILTER,
        "-T",
        "jsonraw",
    ]

    print("Running tshark...")
    print(f"Capture: {CAPTURE_FILE}")
    print(f"Filter: {DISPLAY_FILTER}")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"tshark failed:\n{completed.stderr}"
        )

    if not completed.stdout.strip():
        raise RuntimeError(
            "tshark returned no matching frames"
        )

    return json.loads(completed.stdout)


def clean_hex(value):
    return (
        value
        .replace(":", "")
        .replace(" ", "")
        .replace("\n", "")
        .replace("\r", "")
    )


def find_frame_raw_hex(packet):
    layers = (
        packet
        .get("_source", {})
        .get("layers", {})
    )

    frame_raw = layers.get("frame_raw")

    if isinstance(frame_raw, list):
        if frame_raw:
            return frame_raw[0]

    if isinstance(frame_raw, str):
        return frame_raw

    for field_name, field_value in layers.items():
        if not field_name.endswith("_raw"):
            continue

        if isinstance(field_value, list):
            if not field_value:
                continue
            candidate = field_value[0]
        else:
            candidate = field_value

        if not isinstance(candidate, str):
            continue

        cleaned = clean_hex(candidate)

        if len(cleaned) == EXPECTED_FRAME_SIZE * 2:
            print(f"Using raw field: {field_name}")
            return candidate

    raise ValueError(
        "Unable to locate complete raw frame data"
    )


def expected_addresses():
    addresses = []

    base_address = 0x1E0000

    for packet_index in range(EXPECTED_PACKET_COUNT):
        address = base_address + (
            packet_index * EXPECTED_DATA_SIZE
        )

        address_bytes = bytes(
            [
                0x04,
                (address >> 16) & 0xFF,
                (address >> 8) & 0xFF,
                address & 0xFF,
            ]
        )

        addresses.append(address_bytes)

    return addresses


def extract_candidate_payloads(packets):
    payloads = []

    for frame_index, packet in enumerate(packets):
        raw_hex = find_frame_raw_hex(packet)
        raw_hex = clean_hex(raw_hex)

        frame_bytes = bytes.fromhex(raw_hex)

        if len(frame_bytes) != EXPECTED_FRAME_SIZE:
            raise ValueError(
                f"Frame {frame_index} has "
                f"{len(frame_bytes)} bytes, "
                f"expected {EXPECTED_FRAME_SIZE}"
            )

        payload = frame_bytes[USBPCAP_HEADER_SIZE:]

        if len(payload) != EXPECTED_PAYLOAD_SIZE:
            raise ValueError(
                f"Payload {frame_index} has "
                f"{len(payload)} bytes, "
                f"expected {EXPECTED_PAYLOAD_SIZE}"
            )

        if not payload.startswith(b"\x5A\xA5"):
            continue

        declared_size = int.from_bytes(
            payload[2:4],
            byteorder="little",
        )

        if declared_size != EXPECTED_DATA_SIZE:
            continue

        if payload[4:6] != b"\x07\x64":
            continue

        payloads.append(payload)

    return payloads


def find_complete_sequence(payloads):
    expected = expected_addresses()

    for start_index in range(len(payloads)):
        if payloads[start_index][6:10] != expected[0]:
            continue

        candidate = payloads[
            start_index:
            start_index + EXPECTED_PACKET_COUNT
        ]

        if len(candidate) != EXPECTED_PACKET_COUNT:
            continue

        valid = True

        for packet_index, payload in enumerate(candidate):
            actual_address = payload[6:10]
            expected_address = expected[packet_index]

            if actual_address != expected_address:
                valid = False
                break

        if valid:
            return candidate

    return None


def main():
    if not TSHARK.exists():
        raise FileNotFoundError(
            f"tshark not found: {TSHARK}"
        )

    if not CAPTURE_FILE.exists():
        raise FileNotFoundError(
            f"Capture not found: {CAPTURE_FILE}"
        )

    raw_packets = run_tshark()

    print(f"Matching raw frames: {len(raw_packets)}")

    payloads = extract_candidate_payloads(
        raw_packets
    )

    print(
        f"Valid 2060-byte AULA packets: "
        f"{len(payloads)}"
    )

    complete_sequence = find_complete_sequence(
        payloads
    )

    if complete_sequence is None:
        print()
        print("No complete 150-packet sequence found.")

        if payloads:
            print(
                f"First address: "
                f"{payloads[0][6:10].hex(' ')}"
            )
            print(
                f"Last address:  "
                f"{payloads[-1][6:10].hex(' ')}"
            )

        raise RuntimeError(
            "Expand or adjust the capture time range"
        )

    output_lines = []

    for packet_index, payload in enumerate(
        complete_sequence
    ):
        address = payload[6:10]
        pixel_data = payload[10:-2]
        trailer = payload[-2:]
        unique_values = sorted(set(pixel_data))

        output_lines.append(payload.hex())

        if packet_index < 10:
            print(
                f"Packet {packet_index:3d}: "
                f"address={address.hex(' ')}, "
                f"trailer={trailer.hex(' ')}, "
                f"pixel_unique={unique_values[:16]}"
            )

    OUTPUT_FILE.write_text(
        "\n".join(output_lines) + "\n",
        encoding="ascii",
    )

    print()
    print(
        f"Extracted complete sequence: "
        f"{len(output_lines)} packets"
    )
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc