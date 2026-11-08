import hid

devices = hid.enumerate(0x0C45, 0x800A)

if not devices:
    print("DEVICE_NOT_FOUND")
else:
    for i, d in enumerate(devices):
        print(f"--- Device {i} ---")
        print(f"VID:       {d['vendor_id']:04X}")
        print(f"PID:       {d['product_id']:04X}")
        print(f"Path:      {d['path']}")
        print(f"Interface: {d.get('interface_number')}")
        print(f"UsagePage: {d.get('usage_page')}")
        print(f"Usage:     {d.get('usage')}")
        print(f"Product:   {d.get('product_string')}")
        print()
