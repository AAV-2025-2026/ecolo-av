import serial
import time

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
print("Reading raw bytes...\n")

count = 0
while count < 20:
    data = ser.read(11)
    if len(data) == 11:
        hex_str = ' '.join(f'{b:02X}' for b in data)
        checksum = sum(data[:10]) & 0xFF
        expected = data[10]
        status = "OK" if checksum == expected else f"FAIL (got {checksum:02X})"
        print(f"[{count:02d}] {hex_str}  | chk: {status}")
        count += 1

ser.close()
