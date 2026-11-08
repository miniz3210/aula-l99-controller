import argparse
import sys
import time
from pathlib import Path

import serial
from crccheck.crc import Crc16Arc


WIDTH = 320
HEIGHT = 480

PORT_DEFAULT = "COM8"
BAUD_RATE = 115200

FRAMEBUFFER_SIZE = WIDTH * HEIGHT * 2
DATA_SIZE = 2048
DATA_PACKET_COUNT = 150

BASE_ADDRESS = 0x1E0000
CRC_XOR_OUTPUT = 0x16E5

SERIAL_WRITE_SIZE = 64
SERIAL_WRITE_DELAY = 0.006
DATA_PACKET_DELAY = 0.22
SHORT_COMMAND_DELAY = 0.10
BLOCK_DELAY = 0.25

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

BLACK_CAPTURE_FILE = (
    PROJECT_ROOT / "solid_black_payload_hex.txt"
)

COMMAND_AFTER_64 = bytes.fromhex(
    "5a a5 00 00 0b 66 04 1e "
    "00 00 00 02 00 00 d7 60"
)

COMMAND_AFTER_128 = bytes.fromhex(
    "5a a5 00 00 0b 66 04 20 "
    "00 00 00 02 00 00 08 a3"
)

COMMAND_TRANSFER_END = bytes.fromhex(
    "5a a5 00 00 12 64 04 22 b0 00 "
    "00 00 00 00 00 00 00 00 00 00 00 "
    "0c 0b"
)

COMMAND_FINAL_COMMIT = bytes.fromhex(
    "5a a5 00 00 0b 66 04 22 "
    "00 00 00 00 b0 0b be a4"
)

COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
}


def clamp_8bit(value):
    return max(0, min(255, int(value)))


def rgb_to_565_value(
    red,
    green,
    blue,
    channel_order,
):
    red = clamp_8bit(red)
    green = clamp_8bit(green)
    blue = clamp_8bit(blue)

    red_5 = (red * 31 + 127) // 255
    green_6 = (green * 63 + 127) // 255
    blue_5 = (blue * 31 + 127) // 255

    if channel_order == "rgb":
        high_5 = red_5
        low_5 = blue_5
    elif channel_order == "bgr":
        high_5 = blue_5
        low_5 = red_5
    else:
        raise ValueError(
            f"Unsupported channel order: {channel_order}"
        )

    return (
        (high_5 << 11)
        | (green_6 << 5)
        | low_5
    )


def encode_pixel(
    red,
    green,
    blue,
    pixel_format,
):
    if pixel_format == "rgb565-be":
        channel_order = "rgb"
        byteorder = "big"
    elif pixel_format == "bgr565-be":
        channel_order = "bgr"
        byteorder = "big"
    elif pixel_format == "rgb565-le":
        channel_order = "rgb"
        byteorder = "little"
    elif pixel_format == "bgr565-le":
        channel_order = "bgr"
        byteorder = "little"
    else:
        raise ValueError(
            f"Unsupported pixel format: {pixel_format}"
        )

    value = rgb_to_565_value(
        red,
        green,
        blue,
        channel_order,
    )

    return value.to_bytes(
        2,
        byteorder=byteorder,
    )


def load_official_first_payload():
    if not BLACK_CAPTURE_FILE.exists():
        raise FileNotFoundError(
            "Official black capture not found: "
            f"{BLACK_CAPTURE_FILE}"
        )

    lines = BLACK_CAPTURE_FILE.read_text(
        encoding="ascii"
    ).splitlines()

    for line_number, line in enumerate(
        lines,
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

        if len(packet) != 2060:
            continue

        if packet[:2] != b"\x5A\xA5":
            continue

        if packet[6:10] != bytes.fromhex(
            "04 1e 00 00"
        ):
            continue

        payload = packet[10:-2]

        if len(payload) != DATA_SIZE:
            raise RuntimeError(
                "Official first payload has "
                f"{len(payload)} bytes, "
                f"expected {DATA_SIZE}"
            )

        print(
            "Loaded official first payload "
            f"from line {line_number}"
        )
        print(
            "Official first payload prefix: "
            f"{payload[:32].hex(' ')}"
        )
        print(
            "Official first payload suffix: "
            f"{payload[-32:].hex(' ')}"
        )

        return payload

    raise RuntimeError(
        "Official first framebuffer payload "
        "was not found"
    )


def build_framebuffer(
    color,
    pixel_format,
):
    red, green, blue = color

    pixel = encode_pixel(
        red,
        green,
        blue,
        pixel_format,
    )

    framebuffer = bytearray(
        pixel * (WIDTH * HEIGHT)
    )

    if len(framebuffer) != FRAMEBUFFER_SIZE:
        raise RuntimeError(
            "Generated framebuffer has "
            f"{len(framebuffer)} bytes, "
            f"expected {FRAMEBUFFER_SIZE}"
        )

    official_first_payload = (
        load_official_first_payload()
    )

    framebuffer[0:DATA_SIZE] = (
        official_first_payload
    )

    print(
        f"RGB input: ({red}, {green}, {blue})"
    )
    print(
        f"Encoded pixel: {pixel.hex(' ')}"
    )
    print(
        f"Framebuffer bytes: {len(framebuffer)}"
    )
    print(
        "First 2048 bytes preserved from "
        "official solid-black capture"
    )

    return bytes(framebuffer)


def address_to_bytes(address):
    if address < 0 or address > 0xFFFFFF:
        raise ValueError(
            "Address outside 24-bit range: "
            f"0x{address:X}"
        )

    return bytes(
        [
            0x04,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
        ]
    )


def calculate_data_packet_crc(
    packet_without_crc,
):
    crc_value = Crc16Arc.calc(
        packet_without_crc
    )

    crc_value ^= CRC_XOR_OUTPUT
    crc_value &= 0xFFFF

    return crc_value.to_bytes(
        2,
        byteorder="little",
    )


def build_data_packet(
    packet_index,
    pixel_data,
):
    if len(pixel_data) != DATA_SIZE:
        raise ValueError(
            f"Packet {packet_index} has "
            f"{len(pixel_data)} data bytes, "
            f"expected {DATA_SIZE}"
        )

    address = (
        BASE_ADDRESS
        + packet_index * DATA_SIZE
    )

    header = (
        b"\x5A\xA5"
        + DATA_SIZE.to_bytes(
            2,
            byteorder="little",
        )
        + b"\x07\x64"
        + address_to_bytes(address)
    )

    if len(header) != 10:
        raise RuntimeError(
            f"Header length is {len(header)}, "
            "expected 10"
        )

    packet_without_crc = (
        header + pixel_data
    )

    crc_bytes = (
        calculate_data_packet_crc(
            packet_without_crc
        )
    )

    packet = (
        packet_without_crc
        + crc_bytes
    )

    if len(packet) != 2060:
        raise RuntimeError(
            f"Packet {packet_index} has "
            f"{len(packet)} bytes, "
            "expected 2060"
        )

    return packet


def build_protocol_sequence(framebuffer):
    chunks = []

    for packet_index in range(
        DATA_PACKET_COUNT
    ):
        start = packet_index * DATA_SIZE
        end = start + DATA_SIZE

        pixel_data = framebuffer[start:end]

        packet = build_data_packet(
            packet_index,
            pixel_data,
        )

        chunks.append(packet)

        if packet_index == 63:
            chunks.append(
                COMMAND_AFTER_64
            )

        if packet_index == 127:
            chunks.append(
                COMMAND_AFTER_128
            )

    chunks.append(
        COMMAND_TRANSFER_END
    )

    chunks.append(
        COMMAND_FINAL_COMMIT
    )

    if len(chunks) != 154:
        raise RuntimeError(
            "Protocol sequence has "
            f"{len(chunks)} chunks, "
            "expected 154"
        )

    return chunks


def write_all(
    connection,
    data,
):
    offset = 0

    while offset < len(data):
        part = data[
            offset:
            offset + SERIAL_WRITE_SIZE
        ]

        written = connection.write(part)

        if written != len(part):
            raise RuntimeError(
                f"Wrote {written} of "
                f"{len(part)} bytes "
                f"at offset {offset}"
            )

        offset += written

        time.sleep(
            SERIAL_WRITE_DELAY
        )


def read_available(connection):
    response = bytearray()

    while connection.in_waiting:
        response.extend(
            connection.read(
                connection.in_waiting
            )
        )

        time.sleep(0.01)

    return bytes(response)


def parse_responses(data):
    ok_count = data.count(
        b"\x4F\x4B"
    )

    print(
        f"Response bytes: {len(data)}"
    )
    print(
        f"OK acknowledgments: {ok_count}"
    )

    if data:
        preview_length = min(
            len(data),
            256,
        )

        print(
            "Response preview: "
            + data[:preview_length].hex(" ")
        )

    return ok_count


def send_sequence(
    port,
    chunks,
):
    connection = serial.Serial()

    connection.port = port
    connection.baudrate = BAUD_RATE
    connection.bytesize = (
        serial.EIGHTBITS
    )
    connection.parity = (
        serial.PARITY_NONE
    )
    connection.stopbits = (
        serial.STOPBITS_ONE
    )

    connection.timeout = 0.2
    connection.write_timeout = 5

    connection.xonxoff = False
    connection.rtscts = False
    connection.dsrdtr = False

    total_written = 0
    data_packet_count = 0
    response_data = bytearray()

    try:
        connection.open()

        print(f"Opened: {port}")
        print("Settings: 115200, 8N1")
        print(
            f"Protocol chunks: {len(chunks)}"
        )

        connection.dtr = True
        connection.rts = True

        time.sleep(0.25)

        connection.reset_input_buffer()
        connection.reset_output_buffer()

        for chunk_index, chunk in enumerate(
            chunks,
            start=1,
        ):
            write_all(
                connection,
                chunk,
            )

            total_written += len(chunk)

            if len(chunk) == 2060:
                data_packet_count += 1

                print(
                    "Data packet "
                    f"{data_packet_count:3d}/150, "
                    f"address="
                    f"{chunk[6:10].hex(' ')}, "
                    f"crc="
                    f"{chunk[-2:].hex(' ')}"
                )

                time.sleep(
                    DATA_PACKET_DELAY
                )
            else:
                print(
                    "Short command: "
                    f"{len(chunk)} bytes, "
                    f"{chunk.hex(' ')}"
                )

                time.sleep(
                    SHORT_COMMAND_DELAY
                )

            available_response = (
                read_available(connection)
            )

            if available_response:
                response_data.extend(
                    available_response
                )

            if (
                len(chunk) == 2060
                and data_packet_count
                in (64, 128)
            ):
                time.sleep(
                    BLOCK_DELAY
                )

        print(
            "Waiting for output queue..."
        )

        connection.flush()
        time.sleep(1.0)

        response_data.extend(
            read_available(connection)
        )

        print(
            "Replay completed: "
            f"{total_written} bytes"
        )

        ok_count = parse_responses(
            bytes(response_data)
        )

        if ok_count >= 150:
            print(
                "Framebuffer acknowledgments "
                f"received: {ok_count}"
            )
        elif ok_count > 0:
            print(
                "WARNING: Only "
                f"{ok_count} OK acknowledgments "
                "were found."
            )
        else:
            print(
                "WARNING: No OK "
                "acknowledgments were detected."
            )

    finally:
        if connection.is_open:
            try:
                connection.dtr = False
                connection.rts = False
            except Exception:
                pass

            connection.close()
            print(f"Closed: {port}")


def save_generated_chunks(
    chunks,
    output_path,
):
    lines = [
        chunk.hex()
        for chunk in chunks
    ]

    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="ascii",
    )

    print(
        "Generated stream saved: "
        f"{output_path}"
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Generate and push a solid-color "
            "framebuffer to the AULA L99 "
            "screen while preserving the "
            "official first payload block."
        )
    )

    parser.add_argument(
        "--port",
        default=PORT_DEFAULT,
        help=(
            "Screen virtual COM port. "
            "Default: COM8"
        ),
    )

    parser.add_argument(
        "--color",
        choices=sorted(COLORS),
        default="white",
        help=(
            "Solid test color. "
            "Default: white"
        ),
    )

    parser.add_argument(
        "--format",
        dest="pixel_format",
        choices=[
            "rgb565-be",
            "bgr565-be",
            "rgb565-le",
            "bgr565-le",
        ],
        default="rgb565-be",
        help=(
            "16-bit framebuffer format. "
            "Default: rgb565-be"
        ),
    )

    parser.add_argument(
        "--generate-only",
        action="store_true",
        help=(
            "Generate the protocol stream "
            "without opening the COM port."
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "generated_solid_stream.txt"
        ),
        help=(
            "Output file for generated "
            "protocol chunks."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    color = COLORS[args.color]

    print(
        "AULA L99 solid-color test"
    )
    print()
    print(f"Color:  {args.color}")
    print(f"Format: {args.pixel_format}")
    print(f"Port:   {args.port}")
    print(
        "Template: official first "
        "2048-byte payload"
    )
    print()

    framebuffer = build_framebuffer(
        color,
        args.pixel_format,
    )

    chunks = build_protocol_sequence(
        framebuffer
    )

    output_path = (
        PROJECT_ROOT
        / args.output
    )

    save_generated_chunks(
        chunks,
        output_path,
    )

    if args.generate_only:
        print(
            "Generate-only mode complete."
        )
        return

    print()
    print(
        "WARNING: The official AULA "
        "software must be completely closed."
    )
    print(
        "Sending generated framebuffer..."
    )
    print()

    send_sequence(
        args.port,
        chunks,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(
            "Cancelled by user"
        )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)