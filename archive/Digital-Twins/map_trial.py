import carla
import time
import math
from pyproj import Transformer

# ---------------------------------------------------------
# Connect to CARLA
# ---------------------------------------------------------
client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()
debug = world.debug
blueprint_library = world.get_blueprint_library()
carla_map = world.get_map()

# ---------------------------------------------------------
# GPS points inside Parking Lot 7 (Carleton University)
# ---------------------------------------------------------
mock_gps = [
    (45.387980, -75.695210, 70.0),
    (45.388050, -75.695000, 70.0),
    (45.388120, -75.694800, 70.0),
    (45.388180, -75.694600, 70.0),
    (45.388240, -75.694400, 70.0)
]

# ---------------------------------------------------------
# Projection from your <geoReference> in p7.xodr
# ---------------------------------------------------------
proj_string = (
    "+proj=tmerc +lat_0=45.3889985 +lon_0=-75.6872252 "
    "+k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
)

transformer = Transformer.from_crs("epsg:4326", proj_string, always_xy=True)

# ---------------------------------------------------------
# REFERENCE POINT for alignment
# Replace this with ANY known CARLA coordinate on your map
# ---------------------------------------------------------
carla_ref = carla.Location(
    x=282.414520,
    y=-439.868195,
    z=2.991179
)

gps_ref = mock_gps[0]
lat0, lon0, alt0 = gps_ref

x_raw0, y_raw0 = transformer.transform(lon0, lat0)

offset_x = carla_ref.x - x_raw0
offset_y = carla_ref.y - y_raw0
offset_z = carla_ref.z - alt0

# ---------------------------------------------------------
# Convert GPS → CARLA (with offset)
# ---------------------------------------------------------
carla_points = []

for lat, lon, alt in mock_gps:
    x_raw, y_raw = transformer.transform(lon, lat)
    aligned = carla.Location(
        x=x_raw + offset_x,
        y=y_raw + offset_y,
        z=alt + offset_z
    )
    carla_points.append(aligned)

print("Aligned CARLA points:")
for p in carla_points:
    print(p)

# ---------------------------------------------------------
# Convert CARLA points → lane-centered waypoints
# ---------------------------------------------------------
waypoints = []
for p in carla_points:
    wp = carla_map.get_waypoint(p, project_to_road=True)
    waypoints.append(wp)

# Draw debug points at lane centers
for wp in waypoints:
    debug.draw_point(
        wp.transform.location,
        size=0.3,
        color=carla.Color(0, 255, 0),
        life_time=30.0
    )

# ---------------------------------------------------------
# Spawn vehicle at the first waypoint
# ---------------------------------------------------------
spawn = waypoints[0].transform
spawn.location.z += 0.5  # avoid clipping

vehicle_bp = blueprint_library.filter("vehicle.*model3*")[0]
vehicle = world.try_spawn_actor(vehicle_bp, spawn)

if vehicle is None:
    print("Failed to spawn vehicle")
    exit(1)

print("Vehicle spawned:", vehicle.id)

# Move spectator above vehicle
spectator = world.get_spectator()
spectator.set_transform(
    carla.Transform(
        location=spawn.location + carla.Location(z=50),
        rotation=carla.Rotation(pitch=-90)
    )
)

# ---------------------------------------------------------
# Pure Pursuit Controller
# ---------------------------------------------------------
def pure_pursuit_control(vehicle, target, lookahead=5.0):
    transform = vehicle.get_transform()
    location = transform.location
    yaw = math.radians(transform.rotation.yaw)

    dx = target.x - location.x
    dy = target.y - location.y

    # Transform to vehicle coordinates
    x_v = math.cos(yaw) * dx + math.sin(yaw) * dy
    y_v = -math.sin(yaw) * dx + math.cos(yaw) * dy

    if x_v <= 0.1:
        return 0.0

    curvature = 2 * y_v / (lookahead ** 2)
    steer = max(-1.0, min(1.0, curvature))
    return steer

# ---------------------------------------------------------
# Drive along the waypoint path
# ---------------------------------------------------------
control = carla.VehicleControl()
control.throttle = 0.3
control.brake = 0.0

use_tick = hasattr(world, "tick")

for wp in waypoints:
    target_loc = wp.transform.location
    print("Heading toward:", target_loc)

    for _ in range(400):
        steer = pure_pursuit_control(vehicle, target_loc, lookahead=11.5)
        control.steer = steer
        control.throttle = 0.6
        vehicle.apply_control(control)

        world.wait_for_tick()


# Stop vehicle
control.throttle = 0.0
control.brake = 1.0
vehicle.apply_control(control)

print("Finished path.")

