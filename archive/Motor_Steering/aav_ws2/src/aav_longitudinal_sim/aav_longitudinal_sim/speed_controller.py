import rclpy
from rclpy.node import Node

from geometry_msgs.msg import TwistStamped
from std_msgs.msg import Float32, Float32MultiArray


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


class SpeedController(Node):
    def __init__(self):
        super().__init__('speed_controller')

        # --- control loop settings ---
        self.dt = 0.01  # 100 Hz

        # simple normalized PID: u in [-1, 1]
        self.kp = 2.0
        self.ki = 0.5
        self.kd = 0.0

        self.int_e = 0.0
        self.prev_e = 0.0

        # state from topics
        self.v_ref = 0.0
        self.v_meas = 0.0
        self.have_speed = False

        # ROS I/O
        self.sub_speed = self.create_subscription(
            TwistStamped, 'speed_sim', self.speed_cb, 10
        )
        self.sub_vref = self.create_subscription(
            Float32, 'v_ref', self.vref_cb, 10
        )
        self.pub_cmd = self.create_publisher(
            Float32MultiArray, 'motor_cmd', 10
        )

        self.timer = self.create_timer(self.dt, self.update)

        self.get_logger().info('Speed controller started')

    def speed_cb(self, msg: TwistStamped):
        self.v_meas = float(msg.twist.linear.x)
        self.have_speed = True

    def vref_cb(self, msg: Float32):
        self.v_ref = float(msg.data)

    def update(self):
        if not self.have_speed:
            # wait until we have at least one speed sample
            return

        e = self.v_ref - self.v_meas

        # PID in normalized units
        self.int_e += e * self.dt
        der_e = (e - self.prev_e) / self.dt
        self.prev_e = e

        u = self.kp * e + self.ki * self.int_e + self.kd * der_e

        # clamp to [-1, 1]
        u = clamp(u, -1.0, 1.0)

        # map u -> throttle, brake (0..1)
        if u >= 0.0:
            throttle = u
            brake = 0.0
        else:
            throttle = 0.0
            brake = -u

        msg = Float32MultiArray()
        msg.data = [throttle, brake]
        self.pub_cmd.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SpeedController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
