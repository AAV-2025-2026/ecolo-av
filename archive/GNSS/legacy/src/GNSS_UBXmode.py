import rclpy
from rclpy.node import Node
import serial
from pyubx2 import UBXReader
from sensor_msgs.msg import NavSatFix, Imu
from std_msgs.msg import Float32
from geometry_msgs.msg import TwistStamped, Vector3Stamped
import numpy as np

class GNSSIMUPublisher(Node):
    def __init__(self):
        super().__init__('gnss_imu_publisher')

        # Publishers
        self.gnss_pub = self.create_publisher(NavSatFix, 'gnss/fix', 10)
        self.imu_pub = self.create_publisher(Imu, 'imu/data', 10)
        self.velocity_pub = self.create_publisher(TwistStamped, 'gnss/velocity', 10)
        self.acceleration_pub = self.create_publisher(Vector3Stamped, 'gnss/acceleration', 10)

        # Serial Connection
        self.serial_port = "/dev/ttyACM0"  # Adjust as needed
        self.baud_rate = 115200
        self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
        self.ubr = UBXReader(self.ser, protfilter=2)

        # Timer
        self.create_timer(0.1, self.read_sensor_data)  # 10 Hz

    def read_sensor_data(self):
        raw_data, parsed_data = self.ubr.read()

        if parsed_data:
            msg_type = parsed_data.identity

            if msg_type == "NAV-PVT":  # Fused GNSS Position & Velocity
                gnss_msg = NavSatFix()
                gnss_msg.latitude = parsed_data.lat
                gnss_msg.longitude = parsed_data.lon
                gnss_msg.altitude = parsed_data.hMSL / 1e3
                self.gnss_pub.publish(gnss_msg)

                # Publish velocity
                velocity_msg = TwistStamped()
                velocity_msg.twist.linear.x = parsed_data.velN / 1e3  # 1e3 to convert mm/s to m/s
                velocity_msg.twist.linear.y = parsed_data.velE / 1e3
                velocity_msg.twist.linear.z = parsed_data.velD / 1e3
                self.velocity_pub.publish(velocity_msg)

                self.get_logger().info(f"Published GNSS: {gnss_msg.latitude}, {gnss_msg.longitude}, {gnss_msg.altitude}")
                self.get_logger().info(f"Published Velocity: {velocity_msg.twist.linear.x}, {velocity_msg.twist.linear.y}, {velocity_msg.twist.linear.z}")

            elif msg_type == "ESF-INS":
                x_ang_rate = np.radians(parsed_data.xAngRate)
                y_ang_rate = np.radians(parsed_data.yAngRate)
                z_ang_rate = np.radians(parsed_data.zAngRate)
                
                x_accel = parsed_data.xAccel
                y_accel = parsed_data.yAccel
                z_accel = parsed_data.zAccel
                
                
                ang_vel_msg = Imu()
                ang_vel_msg.angular_velocity.x = x_ang_rate
                ang_vel_msg.angular_velocity.y = y_ang_rate
                ang_vel_msg.angular_velocity.z = z_ang_rate
                
                self.imu_pub.publish(ang_vel_msg)
                self.get_logger().info(f"Published Angular Velocity: {ang_vel_msg.angular_velocity.x}, {ang_vel_msg.angular_velocity.y}, {ang_vel_msg.angular_velocity.z}")

                acc_msg = Vector3Stamped()
                acc_msg.vector.x = x_accel
                acc_msg.vector.y = y_accel
                acc_msg.vector.z = z_accel
                
                self.acceleration_pub.publish(acc_msg)
                self.get_logger().info(f"Published Acceleration: {acc_msg.vector.x}, {acc_msg.vector.y}, {acc_msg.vector.z}")

def main(args=None):
    rclpy.init(args=args)
    node = GNSSIMUPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

