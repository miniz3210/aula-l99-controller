import sys
import time
from pathlib import Path

import serial


PORT = "COM8"
BAUD_RATE = 115200

PACKET_SIZE = 2060
EXPECTED_PACKET_COUNT = 150

WRITE_SIZE = 64
WRITE_DELAY = 0.006
DATA_PACKET_DELAY = 0.22
SHORT_COMMAND_DELAY = 0.10
BLOCK_DELAY = 0.25

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

INPUT_FILE = (
    PROJECT_ROOT / "solid_white_payload_hex.txt"
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
    "ff ff ff ff ff ff ff ff ff ff ff "
    "0e 9f"
)

COMMAND_FINAL_COMMIT = bytes.fromhex(
    "5a a5 00 00 0b 66 04 22 "
    "00 00 00 00 b0 0b be a4"
)


def load_data_packets():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    packets = []

    lines = INPUT_FILE.read_text(
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

        if len(packet) != PACKET_SIZE:
            raise ValueError(
                f"Line {line_number}: packet has "
                f"{len(packet)} bytes, "
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


def validate_addresses(packets):
    base_address = 0x1E0000

    for index, packet in enumerate(packets):
        address = base_address + index * 2048

        expected = bytes(
            [
                0x04,
                (address >> 16) & 0xFF,
                (address >> 8) & 0xFF,
                address & 0xFF,
            ]
        )

        actual = packet[6:10]

        if actual != expected:
            raise ValueError(
                f"Packet {index}: address "
                f"{actual.hex(' ')} does not match "
                f"{expected.hex(' ')}"
            )


def build_sequence(packets):
    chunks = []

    for index, packet in enumerate(packets):
        chunks.append(packet)

        if index == 63:
            chunks.append(COMMAND_AFTER_64)

        if index == 127:
            chunks.append(COMMAND_AFTER_128)

    chunks.append(COMMAND_TRANSFER_END)
    chunks.append(COMMAND_FINAL_COMMIT)

    if len(chunks) != 154:
        raise RuntimeError(
            f"Generated {len(chunks)} chunks, expected 154"
        )

    return chunks


def write_all(connection, data):
    written = connection.write(data)

    if written != len(data):
        raise RuntimeError(
            f"Wrote {written} of {len(data)} bytes"
        )


def read_available(connection):
    result = bytearray()

    while connection.in_waiting:
        result.extend(
            connection.read(connection.in_waiting)
        )
        time.sleep(0.01)

    return bytes(result)


def send_sequence(chunks):
    response = bytearray()
    data_count = 0
    total_written = 0

    connection = serial.Serial(
        port=PORT,
        baudrate=BAUD_RATE,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.2,
        write_timeout=5,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )

    try:
        print(f"Opened: {PORT}")
        print("Settings: 115200, 8N1")
        print(f"Protocol chunks: {len(chunks)}")

        connection.dtr = True
        connection.rts = True

        time.sleep(0.25)

        connection.reset_input_buffer()
        connection.reset_output_buffer()

        for chunk in chunks:
            write_all(connection, chunk)
            total_written += len(chunk)

            if len(chunk) == PACKET_SIZE:
                data_count += 1

                print(
                    f"Data packet {data_count:3d}/150, "
                    f"address={chunk[6:10].hex(' ')}, "
                    f"captured_crc={chunk[-2:].hex(' ')}"
                )

                time.sleep(DATA_PACKET_DELAY)

                if data_count in (64, 128):
                    time.sleep(BLOCK_DELAY)
            else:
                print(
                    f"Short command: {len(chunk)} bytes, "
                    f"{chunk.hex(' ')}"
                )

                time.sleep(SHORT_COMMAND_DELAY)

            incoming = read_available(connection)

            if incoming:
                response.extend(incoming)

        print("Waiting for output queue...")

        connection.flush()
        time.sleep(1.0)

        response.extend(read_available(connection))

        ok_count = bytes(response).count(b"\x4F\x4B")

        print(f"Replay completed: {total_written} bytes")
        print(f"Response bytes: {len(response)}")
        print(f"OK acknowledgments: {ok_count}")

        if response:
            print(
                "Response preview: "
                f"{bytes(response[:256]).hex(' ')}"
            )

        if ok_count >= 150:
            print(
                "Captured framebuffer acknowledgments "
                f"received: {ok_count}"
            )
        else:
            print(
                "WARNING: Expected at least 150 OK "
                "acknowledgments."
            )

    finally:
        if connection.is_open:
            try:
                connection.dtr = False
                connection.rts = False
                time.sleep(0.05)
            except Exception:
                pass

            connection.close()
            print(f"Closed: {PORT}")


def main():
    print("AULA L99 exact solid-black capture replay")
    print(f"Input: {INPUT_FILE}")
    print()

    packets = load_data_packets()
    validate_addresses(packets)

    print(f"Loaded captured packets: {len(packets)}")
    print(
        "First packet: "
        f"{packets[0][:16].hex(' ')}"
    )
    print(
        "Last packet:  "
        f"{packets[-1][:16].hex(' ')}"
    )

    chunks = build_sequence(packets)

    print()
    print(
        "WARNING: Close the official AULA software "
        "before continuing."
    )
    print(
        "Replaying the exact captured solid-black stream."
    )
    print()

    send_sequence(chunks)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled by user")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)