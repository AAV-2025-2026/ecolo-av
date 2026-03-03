#!/usr/bin/env python3

import smbus
import time

# IMU brand: MPU9250

# sudo i2cdetect -l       // shows all possible busses
# sudo i2cdetect -y 1     // shows active addresses on bus #1

# Acceleration: 
"""
Can choose between +-2g for IMU up to +-16g  ... 

+-16g is overkill for a car's acceleration, so let's use use +-4g (check IMU datasheet)
"""


# Gyroscope: 
"""
±250°/s → very sensitive, reads slow turns clearly                          <--- Ideal for Car, use +-250deg/s
±2000°/s → reads extreme spins, but tiny turns are almost invisible
"""

# Summary for sensitivity (according to datasheet):
"""
How many raw counts (LSB) correspond to 1 real-world unit:

For ±4g accelerometer: sensitivity = 8192 LSB/g → 1g = 8192 counts
For ±250°/s gyroscope: sensitivity = 131 LSB/°/s → 1°/s = 131 counts

So divide raw accel values by 16384, and raw gyro values by 131.

Explanation: 
the IMU Analog-to-Digital data is stored in 16-bit signed values (range goes from -32,768 to  32,767)

±4g involves the range -4g to 4g, which is represented -4g is assigned to -32768 (the minimum) and 4g to 32767 (the maximum)

Easy way to see it:
-32768 → -4g
0 → 0g
+32767 → +4g

Divide 32767 by 4, and you get the value that we must divide the raw accel by (which is 8192)
"""
accel_sensitivty_val = 8192
gyro_sensitivity_val = 131


bus = smbus.SMBus(1)    
address = 0x68


# Wake MPU9250
bus.write_byte_data(address, 0x6B, 0)

def read_word(addr):
    high = bus.read_byte_data(address, addr)
    low  = bus.read_byte_data(address, addr+1)
    val  = (high << 8) + low
    if val >= 0x8000:
        val = -((65535 - val) + 1)
    return val

while True:



    # acceleration
    accel_x = read_word(0x3B) /accel_sensitivty_val
    accel_y = read_word(0x3D) /accel_sensitivty_val
    accel_z = read_word(0x3F) /accel_sensitivty_val

    # gyro
    gyro_x = read_word(0x43) /gyro_sensitivity_val
    gyro_y = read_word(0x45) /gyro_sensitivity_val
    gyro_z = read_word(0x47) /gyro_sensitivity_val

    print(
        f"Accel: {accel_x:.4g} {accel_y:.4g} {accel_z:.4g} "
        f"Gyro: {gyro_x:.4g} {gyro_y:.4g} {gyro_z:.4g}"
    )
    
    time.sleep(0.1)