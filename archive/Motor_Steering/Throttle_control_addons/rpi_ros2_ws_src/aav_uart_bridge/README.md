# aav_uart_bridge (RPi5)

ROS 2 node that subscribes to AckermannDrive(Stamped) and sends fixed-length UART frames to an ESP32.

## UART wiring (Pi GPIO UART0)
- Pi TXD (GPIO14) -> ESP32 RX (Serial1 RX pin)
- Pi RXD (GPIO15) -> ESP32 TX (Serial1 TX pin)
- GND -> GND
- Both sides are 3.3V logic (OK).

## Enable UART on Raspberry Pi OS
Use `raspi-config`:
- Interface Options -> Serial Port
  - Disable login shell over serial: YES
  - Enable serial hardware: YES
Reboot.

port is usually `/dev/serial0`.

## Install dependency
```bash
sudo apt-get update
sudo apt-get install -y python3-serial
```

## Build / run (ROS 2 Jazzy)
Remember to source environment first:
```bash
source /opt/ros/jazzy/setup.bash
cd ~/ws
colcon build --symlink-install
source install/setup.bash
ros2 launch aav_uart_bridge bridge.launch.py
```

## Protocol summary
13-byte frames:
AA 55 01 <seq> <flags> <steer_i16> <throttle_u16> <brake_u16> <crc16_u16>
CRC is CRC-16/CCITT-FALSE over bytes 0..10 (everything except the CRC itself).
