# How the ESP32's uplink frames are arriving at legacy_uart_bridge, on
# /vehicle/esp32/uplink_health at 1 Hz, with the bridge's `uplink: true`.

std_msgs/Header header
bool fresh          # a frame came within uplink_timeout
uint32 frames       # good frames since this bridge started
uint32 lost         # gaps in their sequence numbers: frames that never came
uint32 bad          # frames turned down: a CRC, a version, a field
