import rclpy
from rclpy.node import Node

from ackermann_msgs.msg import AckermannDrive
from std_msgs.msg import Float32


class MotorSimNode(Node):
    """
    Simple software-only motor/brake controller sim:

    - Subscribes to /driveData (AckermannDrive)
    - Computes virtual throttle_cmd in [0, 1] and brake_cmd in [0, 1]
      based on acceleration
    - Simulates a first-order vehicle velocity and brake position
    - Publishes:
        /sim/throttle_cmd : Float32
        /sim/brake_cmd    : Float32
        /sim/velocity     : Float32
        /sim/brake_pos    : Float32
    """

    def __init__(self):
        super().__init__('motor_sim_node')

        # Parameters
        self.max_accel = 3.0     # equivalent for full throttle
        self.max_brake = 3.0     # equivalent for full brake
        self.vel_time_const = 0.8    #first-order dynamics
        self.brake_time_const = 0.3  #how fast brake position moves

        # State
        self.last_cmd_throttle = 0.0  
        self.last_cmd_brake = 0.0     
        self.velocity = 0.0           
        self.brake_pos = 0.0          #(0 = release, 1 = full)

        # Publishers
        self.throttle_pub = self.create_publisher(Float32, 'sim/throttle_cmd', 10)
        self.brake_pub    = self.create_publisher(Float32, 'sim/brake_cmd', 10)
        self.vel_pub      = self.create_publisher(Float32, 'sim/velocity', 10)
        self.brake_pos_pub= self.create_publisher(Float32, 'sim/brake_pos', 10)

        # Subscriber
        self.cmd_sub = self.create_subscription(
            AckermannDrive,
            'driveData',           
            self.cmd_callback,
            10
        )

        # Timer(50 Hz)
        self.dt = 0.02
        self.timer = self.create_timer(self.dt, self.update_sim)

        self.get_logger().info('MotorSimNode started, listening on driveData')

    def cmd_callback(self, msg: AckermannDrive):
        """
        Interpret acceleration:
        - accel > 0 => throttle
        - accel < 0 => brake
        Normalize to [0,1].
        """
        accel = msg.acceleration
        if accel >= 0.0:
            throttle = min(accel / self.max_accel, 1.0)
            brake = 0.0
        else:
            throttle = 0.0
            brake = min(-accel / self.max_brake, 1.0)

        self.last_cmd_throttle = throttle
        self.last_cmd_brake = brake

        # Virtual "PWM" commands
        t_msg = Float32()
        t_msg.data = throttle
        self.throttle_pub.publish(t_msg)

        b_msg = Float32()
        b_msg.data = brake
        self.brake_pub.publish(b_msg)

    def update_sim(self):
        """
        Simple plant model:

        dv/dt = (throttle*max_accel - brake*max_brake) - (velocity / vel_time_const)
        d(brake_pos)/dt = (brake_cmd - brake_pos) / brake_time_const
        """
        # velocity update
        accel_effect = (self.last_cmd_throttle * self.max_accel
                        - self.last_cmd_brake * self.max_brake)
        damping = - self.velocity / max(self.vel_time_const, 1e-3)
        dv = (accel_effect + damping) * self.dt
        self.velocity = max(0.0, self.velocity + dv)

        # brake actuator position
        dbrake = (self.last_cmd_brake - self.brake_pos) / max(self.brake_time_const, 1e-3) * self.dt
        self.brake_pos = min(max(self.brake_pos + dbrake, 0.0), 1.0)

        # publish states
        v_msg = Float32()
        v_msg.data = self.velocity
        self.vel_pub.publish(v_msg)

        bp_msg = Float32()
        bp_msg.data = self.brake_pos
        self.brake_pos_pub.publish(bp_msg)


def main(args=None):
    rclpy.init(args=args)
    node = MotorSimNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

