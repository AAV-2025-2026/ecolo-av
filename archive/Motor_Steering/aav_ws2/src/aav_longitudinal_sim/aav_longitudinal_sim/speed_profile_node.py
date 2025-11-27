import os

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from geometry_msgs.msg import TwistStamped


class StepSpeedProfileNode(Node):
    def __init__(self):
        super().__init__('step_speed_profile_node')

        # === PARAMETERS ===
        # Timer period [s] (how often we check & publish)
        self.dt = 0.1  # 10 Hz -> easy to read in terminal

        # Path to the speed profile file (one speed per line, in m/s)
        default_path = os.path.expanduser(
            '~/aav_ws/src/aav_longitudinal_sim/config/speed_profile.txt'
        )
        self.profile_path = self.declare_parameter(
            'profile_path', default_path
        ).get_parameter_value().string_value

        # Tolerance for "reached" [m/s]
        self.tol = self.declare_parameter(
            'reach_tolerance', 0.03
        ).get_parameter_value().double_value

        # Minimum time to stay on each step [s]
        self.min_hold = self.declare_parameter(
            'min_hold_time', 1.0
        ).get_parameter_value().double_value

        # === Load speed profile from file ===
        self.speeds = []
        try:
            with open(self.profile_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    self.speeds.append(float(line))
        except Exception as e:
            self.get_logger().error(
                f'Failed to read speed profile file: {e}'
            )
            self.speeds = [0.0]

        self.get_logger().info(
            f'Loaded {len(self.speeds)} speed samples from {self.profile_path}'
        )

        # Index of current target in the file
        self.index = 0

        # Current measured speed from plant
        self.v_meas = 0.0
        self.have_speed = False

        # Time bookkeeping
        self.time_on_step = 0.0

        # === ROS I/O ===
        self.pub_vref = self.create_publisher(Float32, 'v_ref', 10)
        self.sub_speed = self.create_subscription(
            TwistStamped, 'speed_sim', self.speed_cb, 10
        )

        self.timer = self.create_timer(self.dt, self.update)

    def speed_cb(self, msg: TwistStamped):
        self.v_meas = float(msg.twist.linear.x)
        self.have_speed = True

    def update(self):
        # No profile loaded -> just publish 0
        if len(self.speeds) == 0:
            v_ref = 0.0
        else:
            # Current target speed from the file
            v_ref = self.speeds[self.index]

        # Publish current target every tick (clear steps in /v_ref)
        msg = Float32()
        msg.data = float(v_ref)
        self.pub_vref.publish(msg)

        # If we don't have speed yet, don't advance
        if not self.have_speed or len(self.speeds) == 0:
            return

        # Update time on this step
        self.time_on_step += self.dt

        # Check if we should move to next step
        error = abs(self.v_meas - v_ref)

        if (
            self.time_on_step >= self.min_hold   # held long enough
            and error <= self.tol                # close enough to target
            and self.index < len(self.speeds) - 1
        ):
            # Move to next speed in the file
            self.index += 1
            self.time_on_step = 0.0
            next_v = self.speeds[self.index]
            self.get_logger().info(
                f"Step complete, speed ≈ {self.v_meas:.3f} m/s. "
                f"Advancing to target {next_v:.3f} m/s (line {self.index+1})."
            )


def main(args=None):
    rclpy.init(args=args)
    node = StepSpeedProfileNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

