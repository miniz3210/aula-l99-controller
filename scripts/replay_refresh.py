import sys
import time
from pywinusb import hid

VID = 0x0C45
PID = 0x800A
INTERFACE_MARKER = "&mi_03"
REPORT_ID = 0x00
DELAY_SECONDS = 0.075


def pad64(prefix, suffix=b""):
    padding_length = 64 - len(prefix) - len(suffix)

    if padding_length < 0:
        raise ValueError("Payload exceeds 64 bytes")

    payload = prefix + bytes(padding_length) + suffix

    if len(payload) != 64:
        raise ValueError(
            f"Invalid payload length: {len(payload)}"
        )

    return payload


# Captured from official AULA software:
#
# bmRequestType = 0x21
# bRequest      = 0x09 SET_REPORT
# wValue        = 0x0300 Feature Report ID 0
# wIndex        = 3
# wLength       = 64

PAYLOADS = [
    # Frame 4381
    pad64(
        bytes.fromhex("04 18")
    ),

    # Frame 4531
    pad64(
        bytes.fromhex(
            "04 28 00 00 00 00 00 00 01"
        )
    ),

    # Frame 4663
    pad64(
        bytes.fromhex(
            "00 01 5A 1A 0B 07 09 0D 09 00 06 00"
        ),
        bytes.fromhex("AA 55"),
    ),

    # Frame 4815
    pad64(
        bytes.fromhex("04 02")
    ),
]


def print_payloads():
    for index, payload in enumerate(PAYLOADS, start=1):
        print(
            f"Payload {index}: "
            f"{len(payload)} bytes "
            f"{payload.hex(' ')}"
        )


def find_target():
    devices = hid.HidDeviceFilter(
        vendor_id=VID,
        product_id=PID,
    ).get_devices()

    if not devices:
        raise RuntimeError(
            "No AULA L99 0C45:800A HID devices found"
        )

    for device in devices:
        path = device.device_path.lower()

        if INTERFACE_MARKER not in path:
            continue

        try:
            device.open()

            feature_reports = device.find_feature_reports()

            for report in feature_reports:
                if report.report_id == REPORT_ID:
                    return device, report

            device.close()

        except Exception:
            try:
                device.close()
            except Exception:
                pass
            raise

    raise RuntimeError(
        "AULA L99 MI_03 Feature Report ID 0 not found"
    )


def send_sequence():
    device, report = find_target()

    try:
        report_length = len(report.get_raw_data())

        print(f"Opened: {device.device_path}")
        print(f"Feature report ID: 0x{report.report_id:02X}")
        print(f"pywinusb report length: {report_length}")

        if report_length != 65:
            raise RuntimeError(
                f"Expected a 65-byte pywinusb report, "
                f"but device reports {report_length} bytes"
            )

        for index, payload in enumerate(PAYLOADS, start=1):
            # pywinusb buffer includes the Report ID byte.
            raw_report = [REPORT_ID] + list(payload)

            if len(raw_report) != 65:
                raise RuntimeError(
                    f"Report {index} has invalid raw length "
                    f"{len(raw_report)}"
                )

            report.set_raw_data(raw_report)
            report.send()

            print(
                f"Sent report {index}/4: "
                f"{payload.hex(' ')}"
            )

            if index < len(PAYLOADS):
                time.sleep(DELAY_SECONDS)

        print("Feature-report sequence completed.")

    finally:
        device.close()


if __name__ == "__main__":
    try:
        print_payloads()
        send_sequence()

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)