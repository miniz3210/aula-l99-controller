from collections import Counter
from pathlib import Path
import bz2
import gzip
import lzma
import math
import struct
import zlib

PACKET_SIZE = 2060
HEADER_SIZE = 10
PAYLOAD_SIZE = 2048
PACKET_COUNT = 150
STREAM_SIZE = PAYLOAD_SIZE * PACKET_COUNT

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CAPTURES = {
    "colour": PROJECT_ROOT / "aula_payload_hex.txt",
    "black": PROJECT_ROOT / "solid_black_payload_hex.txt",
}
OUTPUT_DIR = PROJECT_ROOT / "encoding_analysis"


def load_packets(path):
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    packets = []
    for line_number, line in enumerate(path.read_text(encoding="ascii").splitlines(), start=1):
        value = line.strip().replace(":", "").replace(" ", "")
        if not value:
            continue
        try:
            packet = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(f"{path.name}, line {line_number}: invalid hex: {exc}") from exc
        if len(packet) != PACKET_SIZE:
            continue
        if not packet.startswith(b"\x5A\xA5"):
            raise ValueError(f"{path.name}, line {line_number}: invalid magic")
        if packet[2:4] != b"\x00\x08":
            raise ValueError(f"{path.name}, line {line_number}: unexpected length field")
        if packet[4:6] != b"\x07\x64":
            raise ValueError(f"{path.name}, line {line_number}: unexpected command")
        packets.append(packet)

    if len(packets) != PACKET_COUNT:
        raise ValueError(f"{path.name}: expected {PACKET_COUNT} packets, found {len(packets)}")
    return packets


def validate_addresses(packets):
    base_address = 0x1E0000
    for index, packet in enumerate(packets):
        address = base_address + index * PAYLOAD_SIZE
        expected = bytes([0x04, (address >> 16) & 0xFF, (address >> 8) & 0xFF, address & 0xFF])
        actual = packet[6:10]
        if actual != expected:
            raise ValueError(f"Packet {index}: address {actual.hex(' ')} != {expected.hex(' ')}")


def join_payloads(packets):
    stream = b"".join(packet[HEADER_SIZE:-2] for packet in packets)
    if len(stream) != STREAM_SIZE:
        raise ValueError(f"Stream size {len(stream)}, expected {STREAM_SIZE}")
    return stream


def find_last_nonzero(data):
    for index in range(len(data) - 1, -1, -1):
        if data[index] != 0:
            return index
    return -1


def find_first_difference(left, right):
    for index, (left_byte, right_byte) in enumerate(zip(left, right)):
        if left_byte != right_byte:
            return index
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def find_last_difference(left, right):
    limit = min(len(left), len(right))
    for index in range(limit - 1, -1, -1):
        if left[index] != right[index]:
            return index
    if len(left) != len(right):
        return max(len(left), len(right)) - 1
    return None


def entropy(data):
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def decode_descriptor(stream):
    return {
        "raw_0_31": stream[:32].hex(" "),
        "u32_le_0": struct.unpack_from("<I", stream, 0)[0],
        "u32_be_0": struct.unpack_from(">I", stream, 0)[0],
        "u16_le_4": struct.unpack_from("<H", stream, 4)[0],
        "u16_be_4": struct.unpack_from(">H", stream, 4)[0],
        "u16_le_6": struct.unpack_from("<H", stream, 6)[0],
        "u16_be_6": struct.unpack_from(">H", stream, 6)[0],
        "byte_8": stream[8],
        "u32_le_9": struct.unpack_from("<I", stream, 9)[0],
        "u32_be_9": struct.unpack_from(">I", stream, 9)[0],
    }


def find_signatures(data):
    signatures = {
        "JPEG": b"\xFF\xD8\xFF",
        "PNG": b"\x89PNG\r\n\x1A\n",
        "GIF87a": b"GIF87a",
        "GIF89a": b"GIF89a",
        "BMP": b"BM",
        "ZLIB_78_01": b"\x78\x01",
        "ZLIB_78_9C": b"\x78\x9C",
        "ZLIB_78_DA": b"\x78\xDA",
        "GZIP": b"\x1F\x8B",
        "XZ": b"\xFD7zXZ\x00",
    }
    return {name: data.find(signature) for name, signature in signatures.items() if data.find(signature) >= 0}


def try_decompression(data):
    results = []
    functions = [("zlib", zlib.decompress), ("gzip", gzip.decompress), ("bz2", bz2.decompress), ("lzma", lzma.decompress)]
    for offset in (0, 4, 8, 9, 13, 16, 32, 64):
        candidate = data[offset:]
        for name, function in functions:
            try:
                output = function(candidate)
            except Exception:
                continue
            results.append((name, offset, len(output), output[:32].hex(" ")))
    return results


def most_common_words(data, byteorder, limit=20):
    counts = Counter()
    for offset in range(0, len(data) - 1, 2):
        counts[int.from_bytes(data[offset:offset + 2], byteorder=byteorder)] += 1
    return counts.most_common(limit)


def describe_capture(name, stream):
    print("=" * 72)
    print(f"Capture: {name}")
    print("=" * 72)
    print(f"Stream size: {len(stream)}")
    print(f"First 64 bytes: {stream[:64].hex(' ')}")
    print(f"Last 64 bytes:  {stream[-64:].hex(' ')}")
    print()
    print("Candidate descriptor fields")
    for field_name, value in decode_descriptor(stream).items():
        print(f"  {field_name:12s}: {value}")

    last_nonzero = find_last_nonzero(stream)
    used_bytes = last_nonzero + 1 if last_nonzero >= 0 else 0
    print()
    print(f"Last non-zero offset: {last_nonzero}")
    print(f"Used bytes through last non-zero: {used_bytes}")
    print(f"Zero padding after last non-zero: {len(stream) - used_bytes}")
    print(f"Non-zero bytes: {sum(value != 0 for value in stream)}")
    print(f"Whole-stream entropy: {entropy(stream):.6f} bits/byte")
    print(f"Entropy after byte 13: {entropy(stream[13:]):.6f} bits/byte")

    print()
    print("Known signatures")
    signatures = find_signatures(stream)
    if signatures:
        for signature_name, offset in signatures.items():
            print(f"  {signature_name:12s}: offset {offset}")
    else:
        print("  None found")

    print()
    print("Most common 16-bit words, big-endian")
    for value, count in most_common_words(stream, "big"):
        print(f"  0x{value:04X}: {count}")

    print()
    print("Most common 16-bit words, little-endian")
    for value, count in most_common_words(stream, "little"):
        print(f"  0x{value:04X}: {count}")

    print()
    print("Standard decompression attempts")
    attempts = try_decompression(stream)
    if attempts:
        for algorithm, offset, output_size, prefix in attempts:
            print(f"  {algorithm} at offset {offset}: {output_size} bytes, prefix={prefix}")
    else:
        print("  No standard decompressor succeeded")
    print()


def compare_streams(colour, black):
    print("=" * 72)
    print("Colour versus black comparison")
    print("=" * 72)

    differing_offsets = [index for index, pair in enumerate(zip(colour, black)) if pair[0] != pair[1]]
    first_difference = find_first_difference(colour, black)
    last_difference = find_last_difference(colour, black)

    print(f"First differing offset: {first_difference}")
    print(f"Last differing offset:  {last_difference}")
    print(f"Differing byte count:   {len(differing_offsets)}")

    if differing_offsets:
        print()
        print("First 64 differences")
        for offset in differing_offsets[:64]:
            print(f"  offset {offset:8d}: colour=0x{colour[offset]:02X}, black=0x{black[offset]:02X}")

    diff_map = bytearray(len(colour))
    for offset in differing_offsets:
        diff_map[offset] = 0xFF
    diff_file = OUTPUT_DIR / "difference_map.bin"
    diff_file.write_bytes(diff_map)
    print()
    print(f"Saved: {diff_file}")

    if first_difference is not None:
        start = max(0, first_difference - 32)
        end = min(len(colour), first_difference + 96)
        print()
        print("Colour around first difference:")
        print(colour[start:end].hex(" "))
        print()
        print("Black around first difference:")
        print(black[start:end].hex(" "))
    print()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    streams = {}

    for name, capture_file in CAPTURES.items():
        packets = load_packets(capture_file)
        validate_addresses(packets)
        stream = join_payloads(packets)
        streams[name] = stream

        output_file = OUTPUT_DIR / f"{name}_stream.bin"
        output_file.write_bytes(stream)
        print(f"Saved: {output_file}")
        describe_capture(name, stream)

    compare_streams(streams["colour"], streams["black"])
    print("Analysis complete.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
