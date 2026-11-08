import json
import subprocess
from pathlib import Path


TSHARK = Path(
    r"C:\Program Files\Wireshark\tshark.exe"
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CAPTURE_FILE = PROJECT_ROOT / "aula_solid_white.pcapng"
OUTPUT_FILE = PROJECT_ROOT / "solid_white_short_commands.txt"

USBPCAP_HEADER_SIZE = 27

FRAME_NUMBERS = [
    23489,
    23867,
    24005,
    24011,
]


def clean_hex(value):
    return (
        value
        .replace(":", "")
        .replace(" ", "")
        .replace("\r", "")
        .replace("\n", "")
    )


def run_tshark(frame_number):
    command = [
        str(TSHARK),
        "-r",
        str(CAPTURE_FILE),
        "-Y",
        f"frame.number == {frame_number}",
        "-T",
        "jsonraw",
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"tshark failed for frame {frame_number}:\n"
            f"{completed.stderr}"
        )

    if not completed.stdout.strip():
        raise RuntimeError(
            f"No data returned for frame {frame_number}"
        )

    packets = json.loads(completed.stdout)

    if len(packets) != 1:
        raise RuntimeError(
            f"Expected one packet for frame {frame_number}, "
            f"found {len(packets)}"
        )

    return packets[0]


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

    raise RuntimeError(
        "Complete frame_raw field was not found"
    )


def extract_payload(frame_number):
    packet = run_tshark(frame_number)

    raw_hex = find_frame_raw_hex(packet)
    raw_hex = clean_hex(raw_hex)
    frame_bytes = bytes.fromhex(raw_hex)

    if len(frame_bytes) <= USBPCAP_HEADER_SIZE:
        raise RuntimeError(
            f"Frame {frame_number} is too short: "
            f"{len(frame_bytes)} bytes"
        )

    payload = frame_bytes[USBPCAP_HEADER_SIZE:]

    if not payload.startswith(b"\x5A\xA5"):
        raise RuntimeError(
            f"Frame {frame_number} payload does not start "
            f"with 5A A5: {payload[:16].hex(' ')}"
        )

    return frame_bytes, payload


def crc16_arc(data):
    crc = 0x0000

    for byte in data:
        crc ^= byte

        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1

            crc &= 0xFFFF

    return crc


def check_known_crc(payload):
    if len(payload) < 4:
        return None

    calculated = crc16_arc(payload[:-2])
    calculated ^= 0x16E5
    calculated &= 0xFFFF

    stored = int.from_bytes(
        payload[-2:],
        byteorder="little",
    )

    return calculated, stored, calculated == stored


def main():
    if not TSHARK.exists():
        raise FileNotFoundError(
            f"tshark not found: {TSHARK}"
        )

    if not CAPTURE_FILE.exists():
        raise FileNotFoundError(
            f"Capture not found: {CAPTURE_FILE}"
        )

    output_lines = []

    print(f"Capture: {CAPTURE_FILE}")
    print()

    for frame_number in FRAME_NUMBERS:
        frame_bytes, payload = extract_payload(
            frame_number
        )

        crc_result = check_known_crc(payload)

        print(f"Frame:          {frame_number}")
        print(f"USB frame size: {len(frame_bytes)}")
        print(f"Payload size:   {len(payload)}")
        print(f"Payload:        {payload.hex(' ')}")

        if crc_result is not None:
            calculated, stored, matched = crc_result

            print(
                f"Known CRC calc: 0x{calculated:04X}"
            )
            print(
                f"Stored trailer: 0x{stored:04X}"
            )
            print(
                f"Known CRC match: {matched}"
            )

        print()

        output_lines.append(
            f"{frame_number}|"
            f"{len(payload)}|"
            f"{payload.hex()}"
        )

    OUTPUT_FILE.write_text(
        "\n".join(output_lines) + "\n",
        encoding="ascii",
    )

    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc