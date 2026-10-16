"""
Everything carla_adapter asks of a CARLA server, through its Python client. No ROS.

The `carla` module is handed in, not imported here, so this file loads, and its tests run
(test_link.py, with a pretend `carla`), on a computer without CARLA: a Mac, CI. Only
load_carla() imports the real one, when carla_adapter starts.

The client must be the server's own version: the wheel in the server's
PythonAPI/carla/dist/ (CARLA 0.10, Unreal Engine 5), or `pip install carla==0.9.16`
(Unreal Engine 4). Both are for Linux x86_64 and Windows only: there is no macOS client,
so carla_adapter runs on a Linux computer (docs/carla.md).
"""

from __future__ import annotations

import math

from aav_carla import control, frames, georef


def load_carla():
    """Import CARLA's Python client, or say plainly how to get it."""
    try:
        import carla  # noqa: F401 (only here: the package builds and tests without it)
    except ImportError as e:
        raise RuntimeError(
            "no CARLA Python client here (import carla failed). Install the server's own: "
            'pip install <server>/PythonAPI/carla/dist/carla-*-cp312-*.whl (CARLA 0.10), or '
            'pip install carla==0.9.16. Linux x86_64 or Windows only: see docs/carla.md') from e
    return carla


class CarlaLink:
    """One CARLA server, one car on it, and the sensors on the car."""

    def __init__(self, carla, host: str, port: int, timeout: float, log=print):
        self.carla = carla
        self.log = log
        self.client = carla.Client(host, int(port))
        self.client.set_timeout(float(timeout))
        self.world = None
        self.vehicle = None
        self.sensors = []
        self.original_settings = None
        self.sync = False

    def versions(self) -> tuple[str, str]:
        """Return the server's and the client's versions: they must match."""
        return (self.client.get_server_version(), self.client.get_client_version())

    def load(self, town: str = '', osm: str = '', xodr: str = '',
             datum: tuple[float, float] = (0.0, 0.0)) -> str:
        """
        Load the world, and return what was loaded.

        osm: OpenStreetMap XML (the text): converted to OpenDRIVE with our datum's
        projection, then loaded as roads alone. xodr: OpenDRIVE (the text), loaded the same
        way. town: one of the server's maps (Town10HD_Opt...). None of them: keep the world
        the server has. The OpenDRIVE route is CARLA 0.9.x only: 0.10 (Unreal Engine 5)
        can't import OpenDRIVE yet.
        """
        carla = self.carla
        what = 'the loaded world'
        if osm:
            settings = carla.Osm2OdrSettings()
            for key, value in georef.osm_settings(*datum).items():
                setattr(settings, key, value)
            xodr = carla.Osm2Odr.convert(osm, settings)
            what = 'OpenStreetMap, as roads'
        elif xodr:
            what = 'OpenDRIVE, as roads'
        if xodr:
            params = carla.OpendriveGenerationParameters(**georef.OPENDRIVE_PARAMETERS)
            self.world = self.client.generate_opendrive_world(xodr, params)
        elif town:
            self.world = self.client.load_world(town)
            what = town
        else:
            self.world = self.client.get_world()
        return what

    def configure(self, sync: bool, fixed_delta: float) -> None:
        """Run CARLA synchronously (it waits for our tick) at fixed_delta s a step, or not."""
        settings = self.world.get_settings()
        self.original_settings = settings
        new = self.world.get_settings()
        new.synchronous_mode = bool(sync)
        new.fixed_delta_seconds = float(fixed_delta) if sync else None
        self.world.apply_settings(new)
        self.sync = bool(sync)

    def origin_geolocation(self) -> tuple[float, float]:
        """Return the latitude and longitude CARLA gives its world origin."""
        g = self.world.get_map().transform_to_geolocation(self.carla.Location(0.0, 0.0, 0.0))
        return (g.latitude, g.longitude)

    def spawn_transform(self, spawn, frame: frames.SpawnFrame | None = None):
        """
        Return where to spawn the car: a carla.Transform.

        spawn: georef.parse_spawn()'s answer. A place (x, y, yaw in our map frame) needs
        the world frame (frame): it's turned into CARLA's world and dropped onto the road.
        """
        carla = self.carla
        if isinstance(spawn, tuple):
            if frame is None:
                raise ValueError('spawn:=x,y,yaw needs a map lined up with the datum '
                                 '(frame world): use a spawn point number instead')
            x, y, yaw = spawn
            # Our map point = CARLA's (ROS axes) - (frame.x0, frame.y0), as frame.yaw0 = 0.
            cx, cy, _ = frames.ros_to_location(x + frame.x0, y + frame.y0, 0.0)
            road = self.world.get_map().get_waypoint(carla.Location(cx, cy, 0.0))
            z = road.transform.location.z + 0.3 if road is not None else 0.5
            return carla.Transform(carla.Location(cx, cy, z),
                                   carla.Rotation(yaw=frames.ros_to_rotation(0.0, 0.0, yaw)[2]))
        points = self.world.get_map().get_spawn_points()
        if not points:
            raise RuntimeError('this map has no spawn points: use spawn:=x,y,yaw')
        n = spawn or 0
        if n >= len(points):
            raise ValueError(f'spawn:={n}: this map has spawn points 0 to {len(points) - 1}')
        return points[n]

    def spawn(self, vehicle: str, transform, role_name: str):
        """Spawn the car: the blueprint vehicle (or the best of control.CARS) there."""
        library = self.world.get_blueprint_library()
        name = control.pick_car([b.id for b in library.filter('vehicle.*')], vehicle)
        blueprint = library.find(name)
        if blueprint.has_attribute('role_name'):
            blueprint.set_attribute('role_name', role_name)
        self.vehicle = self.world.try_spawn_actor(blueprint, transform)
        if self.vehicle is None:
            raise RuntimeError(f'CARLA could not spawn {name} there: something is in the way, '
                               'or try another spawn point')
        if self.sync:
            self.world.tick()          # the car appears on the next step
        return name

    def geometry(self) -> dict:
        """
        Return the car's own sizes, from CARLA's physics: m and rad.

        rear_axle_x: the rear axle's x in the actor's frame; wheelbase; max_steer (the front
        wheels' limit); ground_z: the bottom of the bounding box (the ground) in the actor's
        frame.
        """
        t = self.vehicle.get_transform()
        wheels = self.vehicle.get_physics_control().wheels
        xy = frames.wheels_in_actor([(w.position.x, w.position.y) for w in wheels],
                                    t.location.x, t.location.y, t.rotation.yaw)
        rear_x, wheelbase = frames.rear_axle(xy)
        box = self.vehicle.bounding_box
        return {'rear_axle_x': rear_x, 'wheelbase': wheelbase,
                'max_steer': math.radians(wheels[0].max_steer_angle),
                'ground_z': box.location.z - box.extent.z}

    def attach(self, sensor, mount: frames.Mount, callback):
        """Attach one sensors.Sensor at mount, calling callback(data) with each reading."""
        carla = self.carla
        blueprint = self.world.get_blueprint_library().find(sensor.blueprint)
        for key, value in sensor.attributes.items():
            if blueprint.has_attribute(key):
                blueprint.set_attribute(key, value)
            else:
                self.log(f'{sensor.blueprint} has no {key}: left as CARLA sets it')
        where = carla.Transform(carla.Location(mount.x, mount.y, mount.z),
                                carla.Rotation(pitch=mount.pitch, yaw=mount.yaw,
                                               roll=mount.roll))
        actor = self.world.spawn_actor(blueprint, where, attach_to=self.vehicle)
        self.sensors.append(actor)
        actor.listen(callback)
        return actor

    def tick(self) -> float:
        """Step the world (synchronous) or wait for its step; return the simulated time (s)."""
        if self.sync:
            self.world.tick()
            snapshot = self.world.get_snapshot()
        else:
            snapshot = self.world.wait_for_tick()
        return snapshot.timestamp.elapsed_seconds

    def readings(self) -> dict:
        """Return the car's transform, velocity and angular velocity: CARLA's numbers."""
        v = self.vehicle
        t = v.get_transform()
        vel = v.get_velocity()
        ang = v.get_angular_velocity()
        return {'location': (t.location.x, t.location.y, t.location.z),
                'rotation': (t.rotation.roll, t.rotation.pitch, t.rotation.yaw),
                'velocity': (vel.x, vel.y, vel.z),
                'angular_velocity': (ang.x, ang.y, ang.z)}

    def front_wheels_deg(self):
        """Return the front wheels' steering (degrees, + right), or None if CARLA can't."""
        where = getattr(self.carla, 'VehicleWheelLocation', None)
        if where is None:
            return None
        try:
            return (self.vehicle.get_wheel_steer_angle(where.FL_Wheel),
                    self.vehicle.get_wheel_steer_angle(where.FR_Wheel))
        except RuntimeError:
            return None

    def pedal_levels(self) -> tuple[float, float]:
        """Return the throttle and brake (0..1) the car has now, whoever set them."""
        c = self.vehicle.get_control()
        return (float(c.throttle), float(c.brake))

    def drive(self, command) -> None:
        """Apply a control.Ackermann or control.Pedals to the car."""
        carla = self.carla
        if isinstance(command, control.Ackermann):
            self.vehicle.apply_ackermann_control(carla.VehicleAckermannControl(
                steer=command.steer, steer_speed=command.steer_speed, speed=command.speed,
                acceleration=command.acceleration, jerk=command.jerk))
        else:
            self.vehicle.apply_control(carla.VehicleControl(
                throttle=command.throttle, steer=command.steer, brake=command.brake,
                hand_brake=command.hand_brake, reverse=command.reverse))

    def close(self) -> None:
        """Take our car and sensors off the server, and give it back its settings."""
        for s in self.sensors:
            try:
                s.stop()
                s.destroy()
            except RuntimeError:
                pass
        self.sensors = []
        if self.vehicle is not None:
            try:
                self.vehicle.destroy()
            except RuntimeError:
                pass
            self.vehicle = None
        if self.original_settings is not None:
            # Synchronous mode left on would freeze the server for the next client.
            try:
                self.world.apply_settings(self.original_settings)
            except RuntimeError:
                pass
            self.original_settings = None
