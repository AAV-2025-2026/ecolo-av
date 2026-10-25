import carla


client = carla.Client("localhost", 2000)
client.set_timeout(10.0)

world = client.get_world()

blueprints = world.get_blueprint_library()

vehicle_bp = blueprints.filter("vehicle.tesla.model3")[0]

spawn_point = carla.Transform(
    carla.Location(
        x=282.414520,
        y=-439.868195,
        z=2.991179
    ),
    carla.Rotation(
        pitch=-2.588102,
        yaw=-97.114471,
        roll=0.000105
    )
)

vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)

if vehicle is None:
    print("Failed to spawn vehicle — maybe something is blocking the spot.")
else:
    print("Vehicle spawned successfully:", vehicle.id)
    print(world.get_map().name)
    

