# Each wheel's speed along the ground, in m/s (its spin times its radius), negative in
# reverse. NaN means that wheel isn't measured: the real car has one encoder for now.
# Published by the backend on /vehicle/wheels.

std_msgs/Header header
float32 front_left
float32 front_right
float32 rear_left
float32 rear_right
