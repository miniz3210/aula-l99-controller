from pathlib import Path
import inspect
import time

from crccheck import crc


PACKET_SIZE = 2060
HEADER_SIZE = 10
PAYLOAD_SIZE = 2048
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
            f"Expected {EXPECTED_PACKET_COUNT} packets, "
            f"found {len(packets)}"
        )

    return packets


def packet_ranges(packet):
    return {
        "header_and_payload": packet[:-2],
        "without_magic": packet[2:-2],
        "from_command": packet[4:-2],
        "from_channel": packet[6:-2],
        "address_and_payload": packet[7:-2],
        "payload_only": packet[
            HEADER_SIZE:
            HEADER_SIZE + PAYLOAD_SIZE
        ],
        "header_only": packet[:HEADER_SIZE],
        "address_only": packet[7:10],
    }


def stored_values(packet):
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
        "big_xor_ffff": big_value ^ 0xFFFF,
        "little_xor_ffff": little_value ^ 0xFFFF,
    }


def crc16_classes():
    classes = []

    for name in dir(crc):
        candidate = getattr(crc, name)

        if not inspect.isclass(candidate):
            continue

        if not name.lower().startswith("crc16"):
            continue

        try:
            width = candidate.width()
        except Exception:
            continue

        if width == 16:
            classes.append((name, candidate))

    classes.sort(key=lambda item: item[0])
    return classes


def reverse_bits_16(value):
    result = 0

    for bit_index in range(16):
        if value & (1 << bit_index):
            result |= 1 << (15 - bit_index)

    return result


def transformed_values(value):
    swapped = (
        ((value & 0x00FF) << 8)
        | ((value & 0xFF00) >> 8)
    )

    reversed_value = reverse_bits_16(value)

    reversed_swapped = (
        ((reversed_value & 0x00FF) << 8)
        | ((reversed_value & 0xFF00) >> 8)
    )

    return {
        "direct": value,
        "byte_swap": swapped,
        "xor_ffff": value ^ 0xFFFF,
        "byte_swap_xor_ffff": swapped ^ 0xFFFF,
        "bit_reverse": reversed_value,
        "bit_reverse_byte_swap": reversed_swapped,
        "bit_reverse_xor_ffff": (
            reversed_value ^ 0xFFFF
        ),
    }


def compare_results(
    calculated_values,
    stored_packet_values,
):
    transform_names = list(
        transformed_values(0).keys()
    )

    stored_names = list(
        stored_packet_values[0].keys()
    )

    matches = {}

    for transform_name in transform_names:
        for stored_name in stored_names:
            key = (
                transform_name,
                stored_name,
            )
            matches[key] = 0

    for calculated, stored in zip(
        calculated_values,
        stored_packet_values,
    ):
        transforms = transformed_values(
            calculated
        )

        for transform_name, transformed in (
            transforms.items()
        ):
            for stored_name, stored_value in (
                stored.items()
            ):
                if transformed == stored_value:
                    key = (
                        transform_name,
                        stored_name,
                    )
                    matches[key] += 1

    return matches


def main():
    start_time = time.perf_counter()

    print(f"Input: {INPUT_FILE}", flush=True)

    packets = load_packets(INPUT_FILE)
    classes = crc16_classes()

    print(f"Packets: {len(packets)}", flush=True)
    print(
        f"CRC-16 classes: {len(classes)}",
        flush=True,
    )
    print(
        f"First trailer: {packets[0][-2:].hex(' ')}",
        flush=True,
    )
    print(flush=True)

    prepared_ranges = {}

    first_ranges = packet_ranges(packets[0])

    for range_name in first_ranges:
        prepared_ranges[range_name] = [
            packet_ranges(packet)[range_name]
            for packet in packets
        ]

    prepared_stored_values = [
        stored_values(packet)
        for packet in packets
    ]

    results = []
    total_classes = len(classes)

    for class_index, (
        crc_name,
        crc_class,
    ) in enumerate(classes, start=1):
        class_start = time.perf_counter()

        print(
            f"[{class_index:02d}/{total_classes:02d}] "
            f"{crc_name}",
            flush=True,
        )

        for range_name, data_items in (
            prepared_ranges.items()
        ):
            calculated_values = []

            failed = False

            for data in data_items:
                try:
                    calculated = (
                        crc_class.calc(data)
                        & 0xFFFF
                    )
                except Exception:
                    failed = True
                    break

                calculated_values.append(
                    calculated
                )

            if failed:
                continue

            matches = compare_results(
                calculated_values,
                prepared_stored_values,
            )

            for (
                transform_name,
                stored_name,
            ), matched in matches.items():
                results.append(
                    (
                        matched,
                        crc_name,
                        range_name,
                        transform_name,
                        stored_name,
                    )
                )

        class_elapsed = (
            time.perf_counter()
            - class_start
        )

        total_elapsed = (
            time.perf_counter()
            - start_time
        )

        print(
            f"    class time: "
            f"{class_elapsed:.2f}s, "
            f"total: {total_elapsed:.2f}s",
            flush=True,
        )

    results.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    print()
    print("Top CRC catalog candidates")
    print()

    for result in results[:50]:
        matched = result[0]
        crc_name = result[1]
        range_name = result[2]
        transform_name = result[3]
        stored_name = result[4]

        print(
            f"{matched:3d}/{len(packets)}  "
            f"{crc_name:30s}  "
            f"{range_name:22s}  "
            f"{transform_name:24s}  "
            f"{stored_name}"
        )

    perfect_matches = [
        result
        for result in results
        if result[0] == len(packets)
    ]

    print()

    if perfect_matches:
        print("Perfect CRC matches found")
        print()

        for result in perfect_matches:
            print(
                f"CRC class:  {result[1]}"
            )
            print(
                f"Data range: {result[2]}"
            )
            print(
                f"Transform:  {result[3]}"
            )
            print(
                f"Stored as:  {result[4]}"
            )
            print()
    else:
        print(
            "No 150/150 standard CRC match found."
        )

        if results:
            best = results[0]

            print()
            print("Best candidate:")
            print(
                f"  Matches:    "
                f"{best[0]}/{len(packets)}"
            )
            print(
                f"  CRC class:  {best[1]}"
            )
            print(
                f"  Data range: {best[2]}"
            )
            print(
                f"  Transform:  {best[3]}"
            )
            print(
                f"  Stored as:  {best[4]}"
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
        raise SystemExit(
            f"ERROR: {exc}"
        ) from exc