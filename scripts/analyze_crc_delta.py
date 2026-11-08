from pathlib import Path
import inspect
import time

from crccheck import crc


PACKET_SIZE = 2060
EXPECTED_PACKET_COUNT = 150

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_FILE = PROJECT_ROOT / "solid_black_payload_hex.txt"


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
            raise ValueError(
                f"Line {line_number}: "
                f"packet length is {len(packet)}, "
                f"expected {PACKET_SIZE}"
            )

        if not packet.startswith(b"\x5A\xA5"):
            raise ValueError(
                f"Line {line_number} does not start with 5A A5"
            )

        packets.append(packet)

    if len(packets) != EXPECTED_PACKET_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PACKET_COUNT} packets, "
            f"found {len(packets)}"
        )

    return packets


def get_crc_classes():
    classes = []

    for name in dir(crc):
        candidate = getattr(crc, name)

        if not inspect.isclass(candidate):
            continue

        if not name.lower().startswith("crc16"):
            continue

        try:
            if candidate.width() != 16:
                continue
        except Exception:
            continue

        classes.append((name, candidate))

    classes.sort(key=lambda item: item[0])

    return classes


def get_ranges(packet):
    return {
        "header_and_payload": packet[:-2],
        "without_magic": packet[2:-2],
        "from_command": packet[4:-2],
        "from_channel": packet[6:-2],
        "address_and_payload": packet[7:-2],
        "payload_only": packet[10:-2],
        "header_only": packet[:10],
        "address_only": packet[6:10],
        "address_3_bytes": packet[7:10],
    }


def stored_variants(packet):
    trailer = packet[-2:]

    big_value = int.from_bytes(
        trailer,
        byteorder="big",
    )

    little_value = int.from_bytes(
        trailer,
        byteorder="little",
    )

    return {
        "big": big_value,
        "little": little_value,
    }


def byte_swap(value):
    return (
        ((value & 0x00FF) << 8)
        | ((value & 0xFF00) >> 8)
    )


def reverse_bits_16(value):
    result = 0

    for bit_index in range(16):
        if value & (1 << bit_index):
            result |= 1 << (15 - bit_index)

    return result


def calculated_variants(value):
    reversed_value = reverse_bits_16(value)

    return {
        "direct": value,
        "byte_swap": byte_swap(value),
        "bit_reverse": reversed_value,
        "bit_reverse_byte_swap": byte_swap(
            reversed_value
        ),
    }


def count_values(values):
    counts = {}

    for value in values:
        counts[value] = counts.get(value, 0) + 1

    return counts


def main():
    start_time = time.perf_counter()

    print(f"Input: {INPUT_FILE}", flush=True)

    packets = load_packets(INPUT_FILE)
    crc_classes = get_crc_classes()

    print(f"Packets: {len(packets)}", flush=True)
    print(
        f"CRC-16 classes: {len(crc_classes)}",
        flush=True,
    )
    print(
        f"First trailer: {packets[0][-2:].hex(' ')}",
        flush=True,
    )
    print(flush=True)

    prepared_ranges = {}

    for range_name in get_ranges(packets[0]):
        prepared_ranges[range_name] = [
            get_ranges(packet)[range_name]
            for packet in packets
        ]

    results = []

    total_classes = len(crc_classes)

    for class_index, (
        crc_name,
        crc_class,
    ) in enumerate(crc_classes, start=1):
        print(
            f"[{class_index:02d}/{total_classes:02d}] "
            f"{crc_name}",
            flush=True,
        )

        for range_name, data_items in (
            prepared_ranges.items()
        ):
            calculated = []

            try:
                for data in data_items:
                    value = crc_class.calc(data) & 0xFFFF
                    calculated.append(value)
            except Exception:
                continue

            for calc_variant_name in (
                calculated_variants(0)
            ):
                calculated_values = [
                    calculated_variants(value)[
                        calc_variant_name
                    ]
                    for value in calculated
                ]

                for stored_name in ("big", "little"):
                    stored_values = [
                        stored_variants(packet)[stored_name]
                        for packet in packets
                    ]

                    xor_deltas = [
                        calc_value ^ stored_value
                        for calc_value, stored_value in zip(
                            calculated_values,
                            stored_values,
                        )
                    ]

                    delta_counts = count_values(
                        xor_deltas
                    )

                    most_common_delta = max(
                        delta_counts,
                        key=delta_counts.get,
                    )

                    xor_matches = delta_counts[
                        most_common_delta
                    ]

                    add_deltas = [
                        (
                            stored_value - calc_value
                        ) & 0xFFFF
                        for calc_value, stored_value in zip(
                            calculated_values,
                            stored_values,
                        )
                    ]

                    add_counts = count_values(
                        add_deltas
                    )

                    most_common_add = max(
                        add_counts,
                        key=add_counts.get,
                    )

                    add_matches = add_counts[
                        most_common_add
                    ]

                    results.append(
                        {
                            "matches": xor_matches,
                            "mode": "xor_delta",
                            "delta": most_common_delta,
                            "crc": crc_name,
                            "range": range_name,
                            "calc_variant": calc_variant_name,
                            "stored": stored_name,
                        }
                    )

                    results.append(
                        {
                            "matches": add_matches,
                            "mode": "add_delta",
                            "delta": most_common_add,
                            "crc": crc_name,
                            "range": range_name,
                            "calc_variant": calc_variant_name,
                            "stored": stored_name,
                        }
                    )

    results.sort(
        key=lambda item: item["matches"],
        reverse=True,
    )

    print()
    print("Top custom-seed / delta candidates")
    print()

    for result in results[:50]:
        print(
            f"{result['matches']:3d}/{len(packets)}  "
            f"{result['crc']:28s}  "
            f"{result['range']:22s}  "
            f"{result['calc_variant']:22s}  "
            f"{result['stored']:6s}  "
            f"{result['mode']:10s}  "
            f"delta=0x{result['delta']:04X}"
        )

    perfect = [
        result
        for result in results
        if result["matches"] == len(packets)
    ]

    print()

    if perfect:
        print("Perfect constant-delta candidates found")
        print()

        for result in perfect:
            print(
                f"CRC:          {result['crc']}\n"
                f"Range:        {result['range']}\n"
                f"Calculation:  {result['calc_variant']}\n"
                f"Stored:       {result['stored']}\n"
                f"Mode:         {result['mode']}\n"
                f"Delta:        0x{result['delta']:04X}\n"
            )
    else:
        print(
            "No 150/150 constant-delta candidate found."
        )

        best = results[0]

        print()
        print("Best candidate:")
        print(
            f"  Matches:     "
            f"{best['matches']}/{len(packets)}"
        )
        print(
            f"  CRC:         {best['crc']}"
        )
        print(
            f"  Range:       {best['range']}"
        )
        print(
            f"  Calculation: {best['calc_variant']}"
        )
        print(
            f"  Stored:      {best['stored']}"
        )
        print(
            f"  Mode:        {best['mode']}"
        )
        print(
            f"  Delta:       0x{best['delta']:04X}"
        )

    elapsed = time.perf_counter() - start_time

    print()
    print(
        f"Completed in {elapsed:.2f} seconds."
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc