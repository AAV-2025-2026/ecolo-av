"""
The IMU's acceleration in Gazebo: what a real IMU on the car would feel. No ROS here.

Gazebo's IMU misses the car's own acceleration (found 15 Oct by the actuator tests):
Gazebo's Ackermann system drives the wheels by speed, and its IMU reads only gravity,
noise and the odd contact bump. Speeding up at 0.6 m/s^2 read 0.00 on average. So
gazebo_adapter replaces the forward and sideways readings with the car's:

    forward  = dv/dt (the actuator model's) - x r^2   speeding up, braking
    left     = v r + x dr/dt                           the turn's centripetal pull

v the speed, r the yaw rate, x how far the IMU sits ahead of the rear axle (imu_link,
vehicle.yaml). Up stays Gazebo's: gravity, and the bumps.
"""


def body_acceleration(accel, speed, yaw_rate, yaw_accel=0.0, x=0.0):
    """Return (forward, left) acceleration (m/s^2) at a point x m ahead of the rear axle."""
    return accel - x * yaw_rate * yaw_rate, speed * yaw_rate + x * yaw_accel
