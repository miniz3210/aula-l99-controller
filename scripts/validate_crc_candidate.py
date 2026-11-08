from pathlib import Path

from crccheck.crc import Crc16Arc


PACKET_SIZE = 2060
EXPECTED_PACKET_COUNT = 150
XOR_OUTPUT = 0x16E5

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CAPTURE_FILES = [
    PROJECT_ROOT / "solid_black_payload_hex.txt",
    PROJECT_ROOT / "aula_payload_hex.txt",
]


def load_packets(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}"
        )

    packets = []

    for line_number, line in enumerate(
        path.read_text(encoding="ascii").splitlines(),
        start=1,
    ):
        value = (
            line.strip()
            .replace(":", "")
            .replace(" ", "")
        )

        if not value:
            continue

        packet = bytes.fromhex(value)

        if len(packet) != PACKET_SIZE:
            continue

        if not packet.startswith(b"\x5A\xA5"):
            raise ValueError(
                f"{path.name}, line {line_number}: "
                "packet does not start with 5A A5"
            )

        packets.append(packet)

    if len(packets) != EXPECTED_PACKET_COUNT:
        raise ValueError(
            f"{path.name}: expected "
            f"{EXPECTED_PACKET_COUNT} data packets, "
            f"found {len(packets)}"
        )

    return packets


def calculate_packet_crc(packet):
    data = packet[:-2]

    crc_value = Crc16Arc.calc(data)
    crc_value ^= XOR_OUTPUT

    return crc_value & 0xFFFF


def validate_capture(path):
    packets = load_packets(path)

    matched = 0
    mismatches = []

    for packet_index, packet in enumerate(packets):
        calculated = calculate_packet_crc(packet)

        stored = int.from_bytes(
            packet[-2:],
            byteorder="little",
        )

        if calculated == stored:
            matched += 1
        else:
            mismatches.append(
                {
                    "index": packet_index,
                    "address": packet[6:10].hex(" "),
                    "calculated": calculated,
                    "stored": stored,
                    "trailer": packet[-2:].hex(" "),
                }
            )

    print(f"Capture: {path.name}")
    print(f"Packets: {len(packets)}")
    print(
        f"Matched: {matched}/{len(packets)}"
    )

    if mismatches:
        print(
            f"Mismatches: {len(mismatches)}"
        )

        for mismatch in mismatches[:10]:
            print(
                f"  Packet {mismatch['index']:3d}, "
                f"address={mismatch['address']}, "
                f"calculated=0x"
                f"{mismatch['calculated']:04X}, "
                f"stored=0x"
                f"{mismatch['stored']:04X}, "
                f"trailer="
                f"{mismatch['trailer']}"
            )
    else:
        print("All packet checksums match.")

    print()

    return matched == len(packets)


def show_first_packet_example(path):
    packets = load_packets(path)
    packet = packets[0]

    raw_crc = Crc16Arc.calc(
        packet[:-2]
    )

    final_crc = raw_crc ^ XOR_OUTPUT

    stored_crc = int.from_bytes(
        packet[-2:],
        byteorder="little",
    )

    generated_bytes = final_crc.to_bytes(
        2,
        byteorder="little",
    )

    print(f"Example from: {path.name}")
    print(
        f"Address:       "
        f"{packet[6:10].hex(' ')}"
    )
    print(
        f"Raw ARC CRC:   "
        f"0x{raw_crc:04X}"
    )
    print(
        f"XOR constant:  "
        f"0x{XOR_OUTPUT:04X}"
    )
    print(
        f"Final CRC:     "
        f"0x{final_crc:04X}"
    )
    print(
        f"Generated:     "
        f"{generated_bytes.hex(' ')}"
    )
    print(
        f"Captured:      "
        f"{packet[-2:].hex(' ')}"
    )
    print(
        f"Stored value:  "
        f"0x{stored_crc:04X}"
    )
    print()


def main():
    print("AULA L99 packet CRC validation")
    print()
    print("Candidate:")
    print("  Algorithm: CRC-16/ARC")
    print("  Input:     packet[:-2]")
    print("  XOR:       0x16E5")
    print("  Storage:   little-endian")
    print()

    all_valid = True

    for capture_file in CAPTURE_FILES:
        valid = validate_capture(
            capture_file
        )

        if not valid:
            all_valid = False

    show_first_packet_example(
        CAPTURE_FILES[0]
    )

    if all_valid:
        print(
            "RESULT: candidate validated across "
            "all captures."
        )
        print(
            "The data-packet checksum algorithm "
            "can be used for generated frames."
        )
    else:
        print(
            "RESULT: candidate did not validate "
            "across all captures."
        )
        print(
            "Do not use this candidate for "
            "generated framebuffer packets yet."
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        raise SystemExit(
            f"ERROR: {exc}"
        ) from exc