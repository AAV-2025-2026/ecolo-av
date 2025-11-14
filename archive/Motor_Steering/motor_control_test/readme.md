# AAV Motor Control Simulation Test

This workspace contains a small ROS 2 (Foxy) simulation used to test the
**motor control logic**.

Instead of driving a physical motor controller, the node
`aav_motor_sim/motor_sim_node`:

- Subscribes to `/driveData` (`ackermann_msgs/AckermannDrive`)
- Converts `acceleration` into normalized **throttle** and **brake** commands
- Simulates first-order vehicle velocity and brake actuator dynamics
- Publishes the internal states on:

  - `/sim/throttle_cmd` 
  - `/sim/brake_cmd` 
  - `/sim/velocity` 
  - `/sim/brake_pos`

This lets us verify motor-control behaviour in different scenarios
(Idle, Acceleration, Braking) entirely in software.

---

## Requirements

- Ubuntu 20.04
- ROS 2 Foxy


- This workspace layout:
  ```text
  aav_ws/
    src/
      ackermann_msgs/
      aav_drive_msg/
      my_custom_message/
      aav_motor_sim/
