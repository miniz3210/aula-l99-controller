import serial
import time

PORT = "COM8"
BAUD = 115200

print(f"Opening {PORT} at {BAUD} baud...")

ser = serial.Serial(
    port=PORT,
    baudrate=BAUD,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=0.05,
    write_timeout=1,
)

print("PORT_OPEN_OK")
print("Listening for 15 seconds. Touch the screen during this period.")

end = time.time() + 15

try:
    while time.time() < end:
        waiting = ser.in_waiting
        if waiting:
            data = ser.read(waiting)
            print(f"RX len={len(data)} hex={data.hex(' ')}")
        time.sleep(0.01)
finally:
    ser.close()
    print("PORT_CLOSED")
