# AULA L99 Touchscreen Reverse Engineering & Stream Deck Bridge

This project documents the hardware architecture, USB serial protocol, and touch events of the built-in 3.98" touchscreen (320x480) on the AULA L99 mechanical keyboard, providing open-source Python scripts to push custom widgets without relying on the official driver.

## Hardware Architecture

The keyboard utilizes a dual-controller architecture over a single USB connection:
* **Keyboard MCU**: HFD / SONiX (VID `0C45`, PID `800A`) - Standard USB HID for keystrokes, RGB lighting, and physical macros.
* **Screen Controller**: LevienTek / Leaguer LT268A / LT2686 (VID `EEEF`, PID `268A`) - Serial COM Port (`USBSER000`, e.g., `COM8`), runs UartTFT-II protocol.
* **Wireless Note**: In 2.4G mode, the keyboard enumerates as Apple Dongle (`05AC:024F`) and drops the serial interface entirely. Direct screen control requires USB wired connection.

## Screen Communication Protocol

### Image Push Protocol
Images must be sent as raw standard JPEG buffers preceded by a 64-byte binary header over the COM port:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 - 0x04 | 5 bytes | Hex | Magic signature + Command: `12 34 56 78 02` |
| 0x05 - 0x07 | 3 bytes | Padding | `00 00 00` |
| 0x08 - 0x0B | 4 bytes | uint32 (LE) | Image Height (480 = `E0 01 00 00`) |
| 0x0C - 0x0F | 4 bytes | uint32 (LE) | Image Width (320 = `40 01 00 00`) |
| 0x10 - 0x37 | 40 bytes | Padding | `00 ... 00` |
| 0x38 - 0x3B | 4 bytes | uint32 (LE) | Flag: `02 00 00 00` |
| 0x3C - 0x3F | 4 bytes | uint32 (LE) | JPEG byte count |

After transmitting the payload, an HID SET_REPORT is sent to `0C45:800A` to trigger the display refresh.

### Hardware Monitor Mechanism
Official driver IPC writes metrics into `data.ini` (`CPU`, `GPU`, `CPU_Temperature`, `GPU_Temperature`, etc.), which `DeviceDriver.exe` reads, overlays onto the UI, and sends to the screen.

## Getting Started
```bash
pip install -r requirements.txt
python scripts/test_push_image.py