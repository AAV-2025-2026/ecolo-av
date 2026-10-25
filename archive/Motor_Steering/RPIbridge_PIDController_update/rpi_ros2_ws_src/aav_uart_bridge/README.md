# aav_uart_bridge

ROS 2 node that subscribes to `AckermannDriveStamped` or `AckermannDrive` and sends framed UART commands to the ESP32.

## Wiring
- Pi TXD (GPIO14 / UART0 TX) -> ESP32 Serial1 RX
- Pi RXD (GPIO15 / UART0 RX) -> ESP32 Serial1 TX
- GND -> GND
- Both sides are 3.3 V logic

## Notes
- Default port is `/dev/serial0`
- Install pyserial:

```bash
sudo apt-get update
sudo apt-get install -y python3-serial
```
