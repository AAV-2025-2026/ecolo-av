import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32


class VrefNode(Node):
    def __init__(self):
        super().__init__('vref_node')
        self.pub = self.create_publisher(Float32, 'v_ref', 10)

        self.dt = 0.01
        self.t = 0.0

        self.timer = self.create_timer(self.dt, self.update)
        self.get_logger().info('v_ref profile node started')

    def update(self):
        # same profile as MATLAB script
        if self.t < 5.0:
            v_ref = 0.2 * self.t           # 0 -> 1 m/s
        elif self.t < 10.0:
            v_ref = 1.0                    # hold 1 m/s
        elif self.t < 15.0:
            v_ref = 1.0 - 0.2 * (self.t - 10.0)  # 1 -> 0
        else:
            v_ref = 0.0

        msg = Float32()
        msg.data = float(v_ref)
        self.pub.publish(msg)

        self.t += self.dt


def main(args=None):
    rclpy.init(args=args)
    node = VrefNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
