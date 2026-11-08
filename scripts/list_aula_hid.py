from pywinusb import hid

VID = 0x0C45
PID = 0x800A

devices = hid.HidDeviceFilter(
    vendor_id=VID,
    product_id=PID,
).get_devices()

if not devices:
    raise SystemExit("No AULA 0C45:800A HID devices found")

print(f"Found {len(devices)} matching HID device(s)\n")

for index, device in enumerate(devices):
    try:
        device.open()

        print(f"Device {index}")
        print(f"  Product:      {device.product_name}")
        print(f"  Vendor:       {device.vendor_name}")
        print(f"  Path:         {device.device_path}")
        print(f"  Instance ID:  {device.instance_id}")

        output_reports = device.find_output_reports()
        feature_reports = device.find_feature_reports()

        print("  Output reports:")
        if output_reports:
            for report in output_reports:
                print(
                    f"    ID=0x{report.report_id:02X} "
                    f"length={len(report.get_raw_data())}"
                )
        else:
            print("    None")

        print("  Feature reports:")
        if feature_reports:
            for report in feature_reports:
                print(
                    f"    ID=0x{report.report_id:02X} "
                    f"length={len(report.get_raw_data())}"
                )
        else:
            print("    None")

        print()

    except Exception as exc:
        print(f"Device {index}: ERROR: {exc}\n")

    finally:
        try:
            device.close()
        except Exception:
            pass