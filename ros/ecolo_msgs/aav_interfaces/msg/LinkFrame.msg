# One frame legacy_uart_bridge wrote on the serial port to the ESP32: what the Pi really
# sent, after every rule in the bridge (docs/designs/2026-11-07_esp32-debug-link_brief.md).
# The values are the frame's own (-1..1), so they can be compared with what the ESP32
# reports it received, with no conversion to hide a fault.
#
# Published by legacy_uart_bridge on /control/car/link_frame, a sample of the frames
# (link_frame_rate_hz, default 10). `written` counts every frame, so counts prove the link
# and the sample only draws the graph.

std_msgs/Header header
uint8 version       # 1, 2 or 3
uint8 counter       # the Orin's counter in the frame; 0 in version 1, which has none
bool armed          # false in version 1, which has no flags
bool estop          # false in version 1, which has no flags
float32 steering    # -1..1
float32 speed       # -1..1
float32 accel       # -1..1; below -0.05 is a brake demand
uint8 cal_mode      # version 3: 0 off, 1 limp, 2 jog
uint16 jog_target   # version 3: counts; 0 otherwise
uint8 check         # the frame's last byte: CRC-8 (2, 3) or sum (1). With the counter, it tells frames apart
uint32 written      # frames written since this bridge started
uint32 write_errors # writes that failed since this bridge started
