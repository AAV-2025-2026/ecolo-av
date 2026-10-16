"""
What Gazebo makes up, for /system/source: each simulated sensor's name and topic.

No ROS here: gazebo_adapter turns the list into an aav_interfaces/DataSource, every entry
SIM. Which entries depend on the world: the road world renders the cameras and the radar
stand-in, and lidar:=true adds the roof lidar (gazebo.launch.py); radar:=false leaves the
radar out.
"""

# The car's own readings: gazebo_adapter's, unless the spine is in the loop (spine:=true),
# when spine_bridge publishes them, and announces them SIM itself.
VEHICLE = [
    ('vehicle', '/vehicle/status'),
    ('odometry', '/vehicle/odom'),
    ('wheels', '/vehicle/wheels'),
]
# Always there: what gazebo_adapter itself publishes.
ALWAYS = [
    ('imu', '/sensors/imu/data_raw'),
    ('gps', '/sensors/gps/fix'),
]
# Only in a world that renders sensors (worlds.has_sensors).
RENDERED = [
    ('camera_front_left', '/sensors/camera/front_left/image_raw'),
    ('camera_front_right', '/sensors/camera/front_right/image_raw'),
    ('camera_rear', '/sensors/camera/rear/image_raw'),
    ('radar', '/sensors/radar/points'),
]
LIDAR = ('lidar', '/sensors/lidar/points')


def simulated(rendered, lidar, radar=True, vehicle=True):
    """Return (name, topic) for everything gazebo_adapter announces in this world."""
    out = (list(VEHICLE) if vehicle else []) + list(ALWAYS)
    if rendered:
        out += [entry for entry in RENDERED if radar or entry[0] != 'radar']
        if lidar:
            out.append(LIDAR)
    return out
