# aav_motor_sim/motor_sim_tester.py

import math
import rclpy
from rclpy.node import Node

from ackermann_msgs.msg import AckermannDrive
from std_msgs.msg import Float32


class MotorSimTester(Node):
    def __init__(self):
        super().__init__('motor_sim_tester')


        self.max_accel = 3.0       
        self.max_brake = 3.0        
        self.vel_time_const = 0.8    

        self.cmd_pub = self.create_publisher(AckermannDrive, 'driveData', 10)

        self.vel_sub = self.create_subscription(
            Float32, 'sim/velocity', self.velocity_callback, 10)
        self.throttle_sub = self.create_subscription(
            Float32, 'sim/throttle_cmd', self.throttle_callback, 10)
        self.brake_sub = self.create_subscription(
            Float32, 'sim/brake_cmd', self.brake_callback, 10)

        self.current_velocity = 0.0
        self.current_throttle = 0.0
        self.current_brake = 0.0

        self.scenarios = [
            {"name": "Idle",           "accel": 0.0,  "duration": 3.0},
            {"name": "ModerateAccel",  "accel": 1.5,  "duration": 6.0},
            {"name": "FullAccel",      "accel": 3.0,  "duration": 6.0},
            {"name": "Brake",          "accel": -1.5, "duration": 4.0},
        ]
        self.current_index = 0
        self.steps_in_scenario = 0

        self.results = []

 
        self.brake_start_velocity = None


        self.dt = 0.05
        self.timer = self.create_timer(self.dt, self.timer_callback)

        self.get_logger().info("MotorSimTester started. "
                               "Make sure motor_sim_node is running.")


    def velocity_callback(self, msg: Float32):
        self.current_velocity = msg.data

    def throttle_callback(self, msg: Float32):
        self.current_throttle = msg.data

    def brake_callback(self, msg: Float32):
        self.current_brake = msg.data


    def timer_callback(self):
        if self.current_index >= len(self.scenarios):
            self.finalize_and_shutdown()
            return

        scenario = self.scenarios[self.current_index]


        cmd = AckermannDrive()
        cmd.speed = 0.0                
        cmd.steering_angle = 0.0
        cmd.acceleration = scenario["accel"]
        self.cmd_pub.publish(cmd)


        if scenario["name"] == "Brake" and self.brake_start_velocity is None:
            self.brake_start_velocity = self.current_velocity

        self.steps_in_scenario += 1
        elapsed = self.steps_in_scenario * self.dt

 
        if elapsed < scenario["duration"]:
            return

        passed, msg = self.evaluate_scenario(scenario["name"], scenario["accel"])
        self.results.append((scenario["name"], passed, msg))
        log_fn = self.get_logger().info if passed else self.get_logger().warn
        log_fn(f"[{scenario['name']}] {'PASS' if passed else 'FAIL'} - {msg}")

 
        self.current_index += 1
        self.steps_in_scenario = 0

        if scenario["name"] == "Brake":
            self.brake_start_velocity = None



    def evaluate_scenario(self, name: str, accel: float):
        v = self.current_velocity

        if name == "Idle":
            if abs(v) < 0.05 and abs(self.current_throttle) < 0.01 and abs(self.current_brake) < 0.01:
                return True, f"velocity={v:.3f} m/s, throttle={self.current_throttle:.2f}, brake={self.current_brake:.2f}"
            else:
                return False, f"expected ~0 m/s & no throttle/brake, got v={v:.3f}, throttle={self.current_throttle:.2f}, brake={self.current_brake:.2f}"


        if accel > 0.0:
            throttle = min(accel / self.max_accel, 1.0)
            expected_v = throttle * self.max_accel * self.vel_time_const
            tolerance = 0.3 

            if abs(v - expected_v) <= tolerance:
                return True, f"v={v:.3f} m/s ≈ expected {expected_v:.3f} m/s"
            else:
                return False, f"v={v:.3f} m/s, expected about {expected_v:.3f} m/s"


        if name == "Brake":
            if self.brake_start_velocity is None:
                if v < 0.2:
                    return True, f"final velocity={v:.3f} m/s (<0.2 m/s)"
                else:
                    return False, f"final velocity={v:.3f} m/s, expected <0.2 m/s"
            else:
                drop = self.brake_start_velocity - v
                if drop > 0.5 * max(self.brake_start_velocity, 1e-3) and v < 0.3:
                    return True, f"velocity dropped from {self.brake_start_velocity:.3f} to {v:.3f} m/s"
                else:
                    return False, f"velocity only dropped from {self.brake_start_velocity:.3f} to {v:.3f} m/s"
        return False, "Unknown scenario"



    def finalize_and_shutdown(self):
        if hasattr(self, "_finished"):
            return
        self._finished = True

        self.get_logger().info("=== MotorSimTester summary ===")
        all_passed = True
        for name, passed, msg in self.results:
            self.get_logger().info(f"{name}: {'PASS' if passed else 'FAIL'} - {msg}")
            if not passed:
                all_passed = False

        if all_passed:
            self.get_logger().info("ALL SCENARIOS PASSED ✅")
        else:
            self.get_logger().warn("Some scenarios FAILED ❌")

        self.timer.cancel()
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = MotorSimTester()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
