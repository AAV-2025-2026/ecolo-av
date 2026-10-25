import rclpy
from rclpy.node import Node

from geometry_msgs.msg import TwistStamped
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32, Float32MultiArray


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


class ImuSpeedController(Node):
    def __init__(self):
        super().__init__('imu_speed_controller')

        # === timing ===
        self.dt = 0.01  # 100 Hz

        # === outer-loop (speed -> desired accel) PID ===
        self.kp_v = 2.0
        self.ki_v = 0.5
        self.kd_v = 0.0

        self.int_e_v = 0.0
        self.prev_e_v = 0.0

        # === inner-loop (accel -> throttle/brake) PID ===
        self.kp_a = 4.0
        self.ki_a = 1.0
        self.kd_a = 0.0

        self.int_e_a = 0.0
        self.prev_e_a = 0.0

        # state from topics
        self.v_ref = 0.0
        self.v_meas = 0.0
        self.a_meas = 0.0
        self.have_speed = False
        self.have_imu = False

        # ROS I/O
        self.sub_speed = self.create_subscription(
            TwistStamped, 'speed_sim', self.speed_cb, 10
        )
        self.sub_vref = self.create_subscription(
            Float32, 'v_ref', self.vref_cb, 10
        )
        self.sub_imu = self.create_subscription(
            Imu, 'imu_sim', self.imu_cb, 10
        )
        self.pub_cmd = self.create_publisher(
            Float32MultiArray, 'motor_cmd', 10
        )

        self.timer = self.create_timer(self.dt, self.update)

        self.get_logger().info('IMU-based speed controller started')

    def speed_cb(self, msg: TwistStamped):
        self.v_meas = float(msg.twist.linear.x)
        self.have_speed = True

    def vref_cb(self, msg: Float32):
        self.v_ref = float(msg.data)

    def imu_cb(self, msg: Imu):
        # use longitudinal accel along x
        self.a_meas = float(msg.linear_acceleration.x)
        self.have_imu = True

    def update(self):
        # wait until we have both speed and imu readings
        if not (self.have_speed and self.have_imu):
            return

        # ===== Outer loop: speed -> desired accel =====
        e_v = self.v_ref - self.v_meas

        self.int_e_v += e_v * self.dt
        der_e_v = (e_v - self.prev_e_v) / self.dt
        self.prev_e_v = e_v

        # a_ref is "what acceleration we want" to fix speed error
        a_ref = self.kp_v * e_v + self.ki_v * self.int_e_v + self.kd_v * der_e_v

        # Optionally clamp a_ref to something reasonable
        a_ref = clamp(a_ref, -2.0, 2.0)  # m/s^2

        # ===== Inner loop: accel (IMU) -> throttle/brake =====
        e_a = a_ref - self.a_meas

        self.int_e_a += e_a * self.dt
        der_e_a = (e_a - self.prev_e_a) / self.dt
        self.prev_e_a = e_a

        u = self.kp_a * e_a + self.ki_a * self.int_e_a + self.kd_a * der_e_a

        # u in [-1, 1]
        u = clamp(u, -1.0, 1.0)

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
    node = ImuSpeedController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
