from pathlib import Path

from PIL import Image


WIDTH = 320
HEIGHT = 480

PACKET_SIZE = 2060
HEADER_SIZE = 10
PIXEL_DATA_SIZE = 2048
CHECKSUM_SIZE = 2

EXPECTED_PACKET_COUNT = 150
EXPECTED_FRAMEBUFFER_SIZE = WIDTH * HEIGHT * 2

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_FILE = SCRIPT_DIR / "aula_payload_hex.txt"
OUTPUT_DIR = SCRIPT_DIR / "decoded_variants"


def load_chunks(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}"
        )

    chunks = []

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
            chunk = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid hex on line {line_number}: {exc}"
            ) from exc

        if not chunk.startswith(b"\x5A\xA5"):
            raise ValueError(
                f"Line {line_number} does not start with 5A A5"
            )

        chunks.append(chunk)

    if not chunks:
        raise ValueError("No protocol chunks found")

    return chunks


def extract_framebuffer(chunks):
    packets = []

    for chunk in chunks:
        if len(chunk) == PACKET_SIZE:
            packets.append(chunk)

    print(f"Total protocol chunks: {len(chunks)}")
    print(f"Framebuffer packets: {len(packets)}")

    if len(packets) != EXPECTED_PACKET_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PACKET_COUNT} packets, "
            f"found {len(packets)}"
        )

    framebuffer_parts = []

    for index, packet in enumerate(packets):
        header = packet[:HEADER_SIZE]

        pixel_start = HEADER_SIZE
        pixel_end = HEADER_SIZE + PIXEL_DATA_SIZE

        pixel_data = packet[pixel_start:pixel_end]
        checksum = packet[pixel_end:pixel_end + CHECKSUM_SIZE]

        if header[:2] != b"\x5A\xA5":
            raise ValueError(
                f"Packet {index} has invalid magic"
            )

        if header[2:4] != b"\x00\x08":
            raise ValueError(
                f"Packet {index} has unexpected length field: "
                f"{header[2:4].hex(' ')}"
            )

        if header[4:6] != b"\x07\x64":
            raise ValueError(
                f"Packet {index} has unexpected command: "
                f"{header[4:6].hex(' ')}"
            )

        if len(pixel_data) != PIXEL_DATA_SIZE:
            raise ValueError(
                f"Packet {index} has {len(pixel_data)} pixel bytes"
            )

        if len(checksum) != CHECKSUM_SIZE:
            raise ValueError(
                f"Packet {index} has invalid checksum length"
            )

        if index < 3:
            print(
                f"Packet {index}: "
                f"header={header.hex(' ')}, "
                f"checksum={checksum.hex(' ')}"
            )

        framebuffer_parts.append(pixel_data)

    framebuffer = b"".join(framebuffer_parts)

    if len(framebuffer) != EXPECTED_FRAMEBUFFER_SIZE:
        raise ValueError(
            f"Framebuffer has {len(framebuffer)} bytes, "
            f"expected {EXPECTED_FRAMEBUFFER_SIZE}"
        )

    print(f"Framebuffer bytes: {len(framebuffer)}")

    return framebuffer


def expand_5_to_8(value):
    return (value << 3) | (value >> 2)


def expand_6_to_8(value):
    return (value << 2) | (value >> 4)


def decode_565(framebuffer, byteorder, channel_order):
    rgb_data = bytearray(WIDTH * HEIGHT * 3)
    output_offset = 0

    for input_offset in range(0, len(framebuffer), 2):
        raw_pixel = framebuffer[input_offset:input_offset + 2]

        pixel = int.from_bytes(
            raw_pixel,
            byteorder=byteorder,
        )

        high_5 = (pixel >> 11) & 0x1F
        green_6 = (pixel >> 5) & 0x3F
        low_5 = pixel & 0x1F

        high_channel = expand_5_to_8(high_5)
        green = expand_6_to_8(green_6)
        low_channel = expand_5_to_8(low_5)

        if channel_order == "RGB":
            red = high_channel
            blue = low_channel
        elif channel_order == "BGR":
            red = low_channel
            blue = high_channel
        else:
            raise ValueError(
                f"Invalid channel order: {channel_order}"
            )

        rgb_data[output_offset] = red
        rgb_data[output_offset + 1] = green
        rgb_data[output_offset + 2] = blue

        output_offset += 3

    image = Image.frombytes(
        "RGB",
        (WIDTH, HEIGHT),
        bytes(rgb_data),
    )

    return image


def decode_555(framebuffer, byteorder, channel_order):
    rgb_data = bytearray(WIDTH * HEIGHT * 3)
    output_offset = 0

    for input_offset in range(0, len(framebuffer), 2):
        raw_pixel = framebuffer[input_offset:input_offset + 2]

        pixel = int.from_bytes(
            raw_pixel,
            byteorder=byteorder,
        )

        high_5 = (pixel >> 10) & 0x1F
        green_5 = (pixel >> 5) & 0x1F
        low_5 = pixel & 0x1F

        high_channel = expand_5_to_8(high_5)
        green = expand_5_to_8(green_5)
        low_channel = expand_5_to_8(low_5)

        if channel_order == "RGB":
            red = high_channel
            blue = low_channel
        elif channel_order == "BGR":
            red = low_channel
            blue = high_channel
        else:
            raise ValueError(
                f"Invalid channel order: {channel_order}"
            )

        rgb_data[output_offset] = red
        rgb_data[output_offset + 1] = green
        rgb_data[output_offset + 2] = blue

        output_offset += 3

    image = Image.frombytes(
        "RGB",
        (WIDTH, HEIGHT),
        bytes(rgb_data),
    )

    return image


def save_image_variants(image, base_name):
    original_path = OUTPUT_DIR / f"{base_name}.png"
    image.save(original_path)

    rotate_90 = image.rotate(90, expand=True)
    rotate_90.save(
        OUTPUT_DIR / f"{base_name}_rotate90.png"
    )

    rotate_180 = image.rotate(180, expand=False)
    rotate_180.save(
        OUTPUT_DIR / f"{base_name}_rotate180.png"
    )

    rotate_270 = image.rotate(270, expand=True)
    rotate_270.save(
        OUTPUT_DIR / f"{base_name}_rotate270.png"
    )

    flip_horizontal = image.transpose(
        Image.Transpose.FLIP_LEFT_RIGHT
    )
    flip_horizontal.save(
        OUTPUT_DIR / f"{base_name}_flip_horizontal.png"
    )

    flip_vertical = image.transpose(
        Image.Transpose.FLIP_TOP_BOTTOM
    )
    flip_vertical.save(
        OUTPUT_DIR / f"{base_name}_flip_vertical.png"
    )

    print(f"Saved variants for: {base_name}")


def main():
    print(f"Input: {INPUT_FILE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    chunks = load_chunks(INPUT_FILE)
    framebuffer = extract_framebuffer(chunks)

    raw_output = OUTPUT_DIR / "framebuffer_rgb16.raw"
    raw_output.write_bytes(framebuffer)

    variants = [
        (
            "rgb565_little_endian",
            decode_565,
            "little",
            "RGB",
        ),
        (
            "bgr565_little_endian",
            decode_565,
            "little",
            "BGR",
        ),
        (
            "rgb565_big_endian",
            decode_565,
            "big",
            "RGB",
        ),
        (
            "bgr565_big_endian",
            decode_565,
            "big",
            "BGR",
        ),
        (
            "rgb555_little_endian",
            decode_555,
            "little",
            "RGB",
        ),
        (
            "bgr555_little_endian",
            decode_555,
            "little",
            "BGR",
        ),
        (
            "rgb555_big_endian",
            decode_555,
            "big",
            "RGB",
        ),
        (
            "bgr555_big_endian",
            decode_555,
            "big",
            "BGR",
        ),
    ]

    print()
    print("Generating image variants...")

    for variant in variants:
        name = variant[0]
        decoder = variant[1]
        byteorder = variant[2]
        channel_order = variant[3]

        image = decoder(
            framebuffer,
            byteorder,
            channel_order,
        )

        save_image_variants(
            image,
            name,
        )

    print()
    print("Decode completed.")
    print(f"Review images in: {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc