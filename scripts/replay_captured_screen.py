import argparse
import sys
import time
from pathlib import Path

import serial


PORT_DEFAULT = "COM8"
BAUD_RATE = 115200

PACKET_SIZE = 2060
EXPECTED_DATA_PACKETS = 150
EXPECTED_CHUNKS = 154

WRITE_SIZE = 64

WRITE_DELAY_DEFAULT = 0.001
DATA_PACKET_DELAY_DEFAULT = 0.008
SHORT_COMMAND_DELAY_DEFAULT = 0.010
BLOCK_DELAY_DEFAULT = 0.020

OPEN_DELAY = 0.250
FINAL_DRAIN_DELAY = 1.000

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = (
    PROJECT_ROOT / "aula_payload_hex.txt"
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Replay a captured AULA L99 screen stream "
            "using paced USB CDC serial writes."
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
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=(
            "Captured hex stream. "
            "Default: project-root "
            "aula_payload_hex.txt"
        ),
    )

    parser.add_argument(
        "--write-delay",
        type=float,
        default=WRITE_DELAY_DEFAULT,
        help=(
            "Delay after each 64-byte serial write. "
            "Default: 0.001"
        ),
    )

    parser.add_argument(
        "--packet-delay",
        type=float,
        default=DATA_PACKET_DELAY_DEFAULT,
        help=(
            "Delay after each 2060-byte data packet. "
            "Default: 0.008"
        ),
    )

    parser.add_argument(
        "--short-delay",
        type=float,
        default=SHORT_COMMAND_DELAY_DEFAULT,
        help=(
            "Delay after each short command. "
            "Default: 0.010"
        ),
    )

    parser.add_argument(
        "--block-delay",
        type=float,
        default=BLOCK_DELAY_DEFAULT,
        help=(
            "Extra delay after data packets "
            "64 and 128. Default: 0.020"
        ),
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "Show block-level progress instead "
            "of every data packet."
        ),
    )

    return parser.parse_args()


def validate_delay(name, value):
    if value < 0 or value > 5:
        raise ValueError(
            f"{name} must be between "
            "0 and 5 seconds"
        )


def load_chunks(path):
    path = path.resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}"
        )

    chunks = []

    lines = path.read_text(
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
            chunk = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid hex on line "
                f"{line_number}: {exc}"
            ) from exc

        if not chunk.startswith(
            b"\x5A\xA5"
        ):
            raise ValueError(
                f"Line {line_number} does not "
                "start with 5A A5"
            )

        chunks.append(chunk)

    data_packets = [
        chunk
        for chunk in chunks
        if len(chunk) == PACKET_SIZE
    ]

    short_commands = [
        chunk
        for chunk in chunks
        if len(chunk) != PACKET_SIZE
    ]

    if len(chunks) != EXPECTED_CHUNKS:
        raise ValueError(
            f"Expected {EXPECTED_CHUNKS} chunks, "
            f"found {len(chunks)}"
        )

    if len(data_packets) != (
        EXPECTED_DATA_PACKETS
    ):
        raise ValueError(
            f"Expected {EXPECTED_DATA_PACKETS} "
            "data packets, "
            f"found {len(data_packets)}"
        )

    if len(short_commands) != 4:
        raise ValueError(
            "Expected 4 short commands, "
            f"found {len(short_commands)}"
        )

    return path, chunks


def write_all(
    connection,
    data,
    write_delay,
):
    offset = 0

    while offset < len(data):
        part = data[
            offset:
            offset + WRITE_SIZE
        ]

        try:
            written = connection.write(part)
        except serial.SerialTimeoutException as exc:
            raise RuntimeError(
                f"Write timeout at offset "
                f"{offset}/{len(data)}, "
                f"block_size={len(part)}, "
                f"out_waiting="
                f"{connection.out_waiting}"
            ) from exc

        if written != len(part):
            raise RuntimeError(
                f"Wrote {written} of "
                f"{len(part)} bytes "
                f"at offset {offset}"
            )

        offset += written

        if write_delay:
            time.sleep(write_delay)


def read_available(connection):
    result = bytearray()

    while connection.in_waiting:
        result.extend(
            connection.read(
                connection.in_waiting
            )
        )

        time.sleep(0.001)

    return bytes(result)


def send_stream(args, chunks):
    connection = serial.Serial(
        port=args.port,
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

    response = bytearray()

    total_written = 0
    data_count = 0
    short_count = 0

    started = time.perf_counter()

    try:
        print(f"Opened: {args.port}")
        print("Settings: 115200, 8N1")
        print(
            f"Protocol chunks: {len(chunks)}"
        )
        print(
            "64-byte write delay: "
            f"{args.write_delay:.3f}s"
        )
        print(
            "Data packet delay: "
            f"{args.packet_delay:.3f}s"
        )

        connection.dtr = True
        connection.rts = True

        time.sleep(OPEN_DELAY)

        connection.reset_input_buffer()
        connection.reset_output_buffer()

        for chunk in chunks:
            write_all(
                connection,
                chunk,
                args.write_delay,
            )

            total_written += len(chunk)

            if len(chunk) == PACKET_SIZE:
                data_count += 1

                if args.quiet:
                    if data_count in (
                        1,
                        32,
                        64,
                        96,
                        128,
                        150,
                    ):
                        print(
                            "Data packet progress: "
                            f"{data_count}/150"
                        )
                else:
                    print(
                        "Data packet "
                        f"{data_count:3d}/150, "
                        "address="
                        f"{chunk[6:10].hex(' ')}, "
                        "crc="
                        f"{chunk[-2:].hex(' ')}"
                    )

                if args.packet_delay:
                    time.sleep(
                        args.packet_delay
                    )

                if (
                    data_count in (64, 128)
                    and args.block_delay
                ):
                    time.sleep(
                        args.block_delay
                    )

            else:
                short_count += 1

                print(
                    "Short command "
                    f"{short_count}/4: "
                    f"{len(chunk)} bytes, "
                    f"{chunk.hex(' ')}"
                )

                if args.short_delay:
                    time.sleep(
                        args.short_delay
                    )

            incoming = read_available(
                connection
            )

            if incoming:
                response.extend(incoming)

        print(
            "Waiting for output queue..."
        )

        connection.flush()

        time.sleep(FINAL_DRAIN_DELAY)

        response.extend(
            read_available(connection)
        )

        elapsed = (
            time.perf_counter()
            - started
        )

        response_bytes = bytes(response)

        ok_count = response_bytes.count(
            b"\x4F\x4B"
        )

        print(
            f"Replay completed: "
            f"{total_written} bytes"
        )

        print(
            f"Response bytes: "
            f"{len(response_bytes)}"
        )

        print(
            f"OK acknowledgments: "
            f"{ok_count}"
        )

        print(
            f"Elapsed seconds: "
            f"{elapsed:.3f}"
        )

        if response_bytes:
            preview = response_bytes[:256]

            print(
                "Response preview: "
                + preview.hex(" ")
            )

        if ok_count >= (
            EXPECTED_DATA_PACKETS
        ):
            print(
                "Framebuffer acknowledgments "
                f"received: {ok_count}"
            )
        else:
            print(
                "WARNING: Expected at least "
                f"{EXPECTED_DATA_PACKETS} "
                "OK acknowledgments, received "
                f"{ok_count}."
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

            print(
                f"Closed: {args.port}"
            )


def main():
    args = parse_arguments()

    validate_delay(
        "write delay",
        args.write_delay,
    )

    validate_delay(
        "packet delay",
        args.packet_delay,
    )

    validate_delay(
        "short delay",
        args.short_delay,
    )

    validate_delay(
        "block delay",
        args.block_delay,
    )

    input_path, chunks = load_chunks(
        args.input
    )

    print(
        "AULA L99 fast "
        "captured-screen replay"
    )

    print(f"Input: {input_path}")

    print(
        f"Loaded chunks: {len(chunks)}"
    )

    print(
        "Total bytes: "
        f"{sum(len(chunk) for chunk in chunks)}"
    )

    print()

    print(
        "WARNING: Close the official AULA "
        "software before replaying."
    )

    print()

    send_stream(
        args,
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