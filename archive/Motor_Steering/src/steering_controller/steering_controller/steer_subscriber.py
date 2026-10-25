
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

class SteeringOutputSubscriber(Node):
    """
    ROS2 node to subscribe to the steering motor command (PWM or normalized -1..1)
    and print/log the output.
    """

    def __init__(self):
        super().__init__('steering_output_subscriber')

        # Subscribe to the motor command topic
        self.subscription = self.create_subscription(
            Float32,
            '/motor/velocity_cmd',  # Topic used in your PWM controller
            self.motor_callback,
            10  # QoS history depth
        )

        self.get_logger().info("Steering output subscriber started.")

    def motor_callback(self, msg: Float32):
        """
        Callback function to handle incoming motor command.
        """
        pwm_cmd = msg.data
        if pwm_cmd > 0:
            direction = "EXTEND"
        elif pwm_cmd < 0:
            direction = "RETRACT"
        else:
            direction = "STOP"

        # Log the command
        self.get_logger().info(f"Steering motor command: {pwm_cmd:.3f} ({direction})")


def main(args=None):
    rclpy.init(args=args)
    node = SteeringOutputSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
