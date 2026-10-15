# The front wheels' speeds, from the wheel nodes on the CAN bus
# (0x200 WHEEL_SPEED_L, 0x201 WHEEL_SPEED_R, firmware/can/aav.dbc).
# Published by aav_spine's spine_bridge on /vehicle/wheel_speed, about 100 Hz.

std_msgs/Header header       # frame_id base_link

float32 left                 # m/s, the left front tyre over the ground, negative in reverse
float32 right                # m/s, the right front tyre
bool left_fresh              # false: no valid frame from that wheel lately; ignore its speed
bool right_fresh
bool direction_measured      # false: the sign comes from the drive direction, because
                             # one Hall sensor can't tell which way the wheel turns
uint16 left_pulses           # Hall sensor pulses so far, wrap at 65536 (to check the
uint16 right_pulses          # speed, or calibrate the radius, from a bag)
