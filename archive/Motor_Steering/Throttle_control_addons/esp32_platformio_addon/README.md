# ESP32 UART actuator firmware(Replace miscro OS)


- Copy `src/esp32_uart_pcb/` into `src/`
- Add the new `[env:esp32_uart_pcb]` section to `platformio.ini`

This firmware:
- Reads UART frames from Raspberry Pi (Serial1)
- Drives steering/brake via JrkG2 over I2C
- Drives throttle via DAC over I2C
- Has a watchdog: if frames stop arriving, throttle=0 and brake=0

## platformio.ini snippet to add

```ini
[env:esp32_uart_pcb]
platform = espressif32
board = sparkfun_esp32micromod
framework = arduino
lib_deps =
  SPI
  Wire
  pololu/JrkG2@^1.1.0
  bmellink/IBusBM@^1.1.4
  hideakitai/PCA95x5@^0.1.3
build_src_filter =
  +<esp32_uart_pcb/>
  +<esp32_ros_pcb/hardware_fns.cpp>
  +<esp32_ros_pcb/motor_ctrl/>
upload_port =
```

## UART pins
By default the code uses `Serial1` with `RX1/TX1`.
Connect Pi UART0 to those pins.
