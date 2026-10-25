# The RC transmitter, as the car's ESP32 reads it from its receiver (iBUS), sent up the
# serial link in its uplink frame (TODO 48, 50). Published by legacy_uart_bridge on
# /vehicle/rc, 50 Hz, only while the uplink is on. The channels, their middles and
# their travel stay in the firmware (ibus RcMap): ROS gets the meaning, not the pulses.

std_msgs/Header header

# The transmitter's mode switch (CH6). Three positions: a proposal for the team and the
# hardware lead (docs/decisions.md); a two-position switch gives computer or RC direct.
uint8 SWITCH_NONE=0          # no RC signal: the receiver silent, or the switch out of range
uint8 SWITCH_COMPUTER=1      # the computer drives; the sticks do nothing
uint8 SWITCH_RC_VIA_ROS=2    # a person drives with the sticks, through ROS (rc_driver)
uint8 SWITCH_RC_DIRECT=3     # a person drives with the sticks, straight from the ESP32
uint8 mode_switch

float32 throttle             # -1..1, + forward: the throttle stick, signed by the gear switch
float32 steering             # -1..1, + left: the steering stick
bool brake                   # the gear switch is on brake
