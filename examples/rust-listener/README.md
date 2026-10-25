# rust-listener: a first ROS 2 node in Rust

Prints what ego tells the car to do (`/ego/actuator_cmd`), 50 times a second.

```bash
pixi run turtle            # terminal 1: the stack, with turtlesim as the car
pixi run keyboard          # terminal 2: drive
pixi run rust-listener     # terminal 3: this node
```

- `rclrs` (writing nodes) and `ros-env` (the message types) come from crates.io.
- The message code itself ships with Jazzy: `ros-env` finds it on `AMENT_PREFIX_PATH`,
  ours (`aav_interfaces`) included. So `use ros_env::aav_interfaces::msg::VehicleStatus;`
  works too.
- It's plain Cargo: colcon doesn't build it. The first build downloads and compiles
  about 100 crates (under a minute); after that, a build takes seconds.
