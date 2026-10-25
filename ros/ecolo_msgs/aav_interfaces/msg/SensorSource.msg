# One part of the data, and where it comes from: the real car, a simulator, the bench's
# stand-ins, or a recording. An entry of aav_interfaces/DataSource, on /system/source.

uint8 REAL=0      # a real device on the real car
uint8 SIM=1       # a simulator: Gazebo, turtlesim
uint8 BENCH=2     # the bench's stand-ins (aav_bench, spine_sim)
uint8 REPLAY=3    # a recording, played back (ros2 bag play)

string name       # what it is: imu, gps, camera_front_left, radar, lidar, vehicle...
string topic      # its main topic, e.g. /sensors/imu/data_raw ('' if it has none)
uint8 source      # REAL, SIM, BENCH or REPLAY
