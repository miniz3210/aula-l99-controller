from pathlib import Path


PACKET_SIZE = 2060
HEADER_SIZE = 10
PAYLOAD_SIZE = 2048
CHECKSUM_SIZE = 2
EXPECTED_PACKET_COUNT = 150

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_FILE = PROJECT_ROOT / "aula_payload_hex.txt"


def load_packets(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}"
        )

    packets = []

    lines = path.read_text(
        encoding="ascii"
    ).splitlines()

    for line_number, line in enumerate(lines, start=1):
        value = line.strip()
        value = value.replace(":", "")
        value = value.replace(" ", "")

        if not value:
            continue

        try:
            packet = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid hex on line {line_number}: {exc}"
            ) from exc

        if len(packet) == PACKET_SIZE:
            packets.append(packet)

    if len(packets) != EXPECTED_PACKET_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PACKET_COUNT} data packets, "
            f"found {len(packets)}"
        )

    return packets


def crc16_generic(
    data,
    polynomial,
    initial,
    reflect_input,
    reflect_output,
    xor_output,
):
    crc = initial

    if reflect_input:
        for byte in data:
            crc ^= byte

            for _ in range(8):
                if crc & 0x0001:
                    crc = (
                        (crc >> 1) ^ polynomial
                    )
                else:
                    crc >>= 1

                crc &= 0xFFFF
    else:
        for byte in data:
            crc ^= byte << 8

            for _ in range(8):
                if crc & 0x8000:
                    crc = (
                        (crc << 1) ^ polynomial
                    )
                else:
                    crc <<= 1

                crc &= 0xFFFF

    if reflect_output != reflect_input:
        crc = reflect_16(crc)

    return crc ^ xor_output


def reflect_16(value):
    result = 0

    for bit_index in range(16):
        if value & (1 << bit_index):
            result |= 1 << (15 - bit_index)

    return result


def crc16_modbus(data):
    return crc16_generic(
        data=data,
        polynomial=0xA001,
        initial=0xFFFF,
        reflect_input=True,
        reflect_output=True,
        xor_output=0x0000,
    )


def crc16_ibm(data):
    return crc16_generic(
        data=data,
        polynomial=0xA001,
        initial=0x0000,
        reflect_input=True,
        reflect_output=True,
        xor_output=0x0000,
    )


def crc16_usb(data):
    return crc16_generic(
        data=data,
        polynomial=0xA001,
        initial=0xFFFF,
        reflect_input=True,
        reflect_output=True,
        xor_output=0xFFFF,
    )


def crc16_ccitt_false(data):
    return crc16_generic(
        data=data,
        polynomial=0x1021,
        initial=0xFFFF,
        reflect_input=False,
        reflect_output=False,
        xor_output=0x0000,
    )


def crc16_xmodem(data):
    return crc16_generic(
        data=data,
        polynomial=0x1021,
        initial=0x0000,
        reflect_input=False,
        reflect_output=False,
        xor_output=0x0000,
    )


def crc16_kermit(data):
    return crc16_generic(
        data=data,
        polynomial=0x8408,
        initial=0x0000,
        reflect_input=True,
        reflect_output=True,
        xor_output=0x0000,
    )


def crc16_x25(data):
    return crc16_generic(
        data=data,
        polynomial=0x8408,
        initial=0xFFFF,
        reflect_input=True,
        reflect_output=True,
        xor_output=0xFFFF,
    )


def additive_16(data):
    return sum(data) & 0xFFFF


def additive_words_le(data):
    total = 0

    for offset in range(0, len(data), 2):
        word_bytes = data[offset:offset + 2]

        if len(word_bytes) == 1:
            word_bytes += b"\x00"

        total += int.from_bytes(
            word_bytes,
            byteorder="little",
        )

    return total & 0xFFFF


def additive_words_be(data):
    total = 0

    for offset in range(0, len(data), 2):
        word_bytes = data[offset:offset + 2]

        if len(word_bytes) == 1:
            word_bytes += b"\x00"

        total += int.from_bytes(
            word_bytes,
            byteorder="big",
        )

    return total & 0xFFFF


def ones_complement_16(data):
    return (~additive_16(data)) & 0xFFFF


def xor_16(data):
    value = 0

    for byte in data:
        value ^= byte

    return value & 0xFFFF


def get_ranges(packet):
    return {
        "header_and_payload": packet[:-2],
        "from_length_field": packet[2:-2],
        "from_command": packet[4:-2],
        "from_channel": packet[6:-2],
        "address_and_payload": packet[7:-2],
        "payload_only": packet[
            HEADER_SIZE:
            HEADER_SIZE + PAYLOAD_SIZE
        ],
    }


def checksum_values(packet):
    checksum = packet[-2:]

    return {
        "stored_big_endian": int.from_bytes(
            checksum,
            byteorder="big",
        ),
        "stored_little_endian": int.from_bytes(
            checksum,
            byteorder="little",
        ),
    }


def main():
    print(f"Input: {INPUT_FILE}")

    packets = load_packets(INPUT_FILE)

    algorithms = {
        "CRC-16/MODBUS": crc16_modbus,
        "CRC-16/IBM": crc16_ibm,
        "CRC-16/USB": crc16_usb,
        "CRC-16/CCITT-FALSE": crc16_ccitt_false,
        "CRC-16/XMODEM": crc16_xmodem,
        "CRC-16/KERMIT": crc16_kermit,
        "CRC-16/X25": crc16_x25,
        "Additive bytes": additive_16,
        "Additive words LE": additive_words_le,
        "Additive words BE": additive_words_be,
        "One's complement bytes": ones_complement_16,
        "XOR bytes": xor_16,
    }

    results = []

    first_packet = packets[0]

    print()
    print(
        "First packet checksum bytes: "
        f"{first_packet[-2:].hex(' ')}"
    )

    for range_name in get_ranges(first_packet):
        for algorithm_name, algorithm in algorithms.items():
            for stored_order in (
                "stored_big_endian",
                "stored_little_endian",
            ):
                matched = 0

                for packet in packets:
                    data = get_ranges(packet)[range_name]
                    calculated = algorithm(data)
                    stored = checksum_values(packet)[stored_order]

                    if calculated == stored:
                        matched += 1

                results.append(
                    (
                        matched,
                        range_name,
                        algorithm_name,
                        stored_order,
                    )
                )

    results.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    print()
    print("Top checksum candidates")
    print()

    for result in results[:30]:
        matched = result[0]
        range_name = result[1]
        algorithm_name = result[2]
        stored_order = result[3]

        print(
            f"{matched:3d}/{len(packets)}  "
            f"{algorithm_name:24s}  "
            f"{range_name:20s}  "
            f"{stored_order}"
        )

    perfect_matches = [
        result
        for result in results
        if result[0] == len(packets)
    ]

    print()

    if perfect_matches:
        print("Perfect matches found:")

        for result in perfect_matches:
            print(
                f"  {result[2]} | "
                f"{result[1]} | "
                f"{result[3]}"
            )
    else:
        print("No 150/150 match found.")
        print(
            "Next step: parameter search for polynomial, "
            "initial value, or protocol-specific checksum."
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc