#!/usr/bin/env python3
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

import smbus



class Mpu9250ImuNode(Node):
    def __init__(self):
        super().__init__("sensor_mpu9250_imu_node")

        # --- IMU settings ---
        self.accel_sensitivity = 8192.0   # LSB/g  (±4g)
        self.gyro_sensitivity = 131.0     # LSB/(deg/s) (±250°/s)
        self.bus = smbus.SMBus(1)
        self.address = 0x68

        # Wake up MPU9250 (clear sleep bit)
        # Power management register 0x6B: set to 0 to wake up
        self.bus.write_byte_data(self.address, 0x6B, 0)

        # --- ROS 2 publisher ---
        self.publisher_ = self.create_publisher(Imu, "/imu/data", 10)

        # Timer: 0.1s -> 10 Hz
        self.timer_period = 0.1
        self.timer = self.create_timer(self.timer_period, self.timer_callback)

        self.get_logger().info("MPU9250 IMU node started, publishing on /imu/data")

    # ---------- Low-level IMU helpers ----------

    def read_word(self, reg_addr: int) -> int:
        """Read a signed 16-bit word from two registers (high, low)."""
        high = self.bus.read_byte_data(self.address, reg_addr)
        low = self.bus.read_byte_data(self.address, reg_addr + 1)
        val = (high << 8) + low
        # Convert from unsigned to signed
        if val >= 0x8000:
            val = -((65535 - val) + 1)
        return val

    def read_accel_gyro(self):
        """Read accel (g) and gyro (deg/s) from the IMU."""
        # Accel registers: X=0x3B, Y=0x3D, Z=0x3F
        accel_x_raw = self.read_word(0x3B)
        accel_y_raw = self.read_word(0x3D)
        accel_z_raw = self.read_word(0x3F)

        # Gyro registers: X=0x43, Y=0x45, Z=0x47
        gyro_x_raw = self.read_word(0x43)
        gyro_y_raw = self.read_word(0x45)
        gyro_z_raw = self.read_word(0x47)

        # Convert raw -> physical units
        # Accel: raw / sensitivity -> g; then g -> m/s^2
        g_to_m_s2 = 9.80665
        accel_x = (accel_x_raw / self.accel_sensitivity) * g_to_m_s2
        accel_y = (accel_y_raw / self.accel_sensitivity) * g_to_m_s2
        accel_z = (accel_z_raw / self.accel_sensitivity) * g_to_m_s2

        # Gyro: raw / sensitivity -> deg/s; then deg/s -> rad/s
        deg_to_rad = math.pi / 180.0
        gyro_x = (gyro_x_raw / self.gyro_sensitivity) * deg_to_rad
        gyro_y = (gyro_y_raw / self.gyro_sensitivity) * deg_to_rad
        gyro_z = (gyro_z_raw / self.gyro_sensitivity) * deg_to_rad

        return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z

    # ---------- Timer callback (runs at 10 Hz) ----------

    def timer_callback(self):
        try:
            ax, ay, az, gx, gy, gz = self.read_accel_gyro()
        except OSError as e:
            # I2C read error – don't crash the node, just log it
            self.get_logger().error(f"I2C read error from MPU9250: {e}")
            return

        msg = Imu()

        # Header
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "imu_link"   # change if your TF frame is named differently

        # Orientation not computed here -> set covariance[0] = -1 as per ROS convention
        msg.orientation_covariance[0] = -1.0

        # Angular velocity (rad/s)
        msg.angular_velocity.x = gx
        msg.angular_velocity.y = gy
        msg.angular_velocity.z = gz
        # Optional: set covariance if you have it, else leave default 0

        # Linear acceleration (m/s^2)
        msg.linear_acceleration.x = ax
        msg.linear_acceleration.y = ay
        msg.linear_acceleration.z = az
        # Optional: set covariance if you have it, else leave default 0

        self.publisher_.publish(msg)


        #Optional debug print (comment out if spammy)
        self.get_logger().info(
            f"Accel: {ax:.3f} {ay:.3f} {az:.3f} | Gyro: {gx:.3f} {gy:.3f} {gz:.3f}"
        )


def main(args=None):

    rclpy.init(args=args)
    node = Mpu9250ImuNode()
    try:
        rclpy.spin(node)   # Keep node alive until Ctrl+C
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()



if __name__ == "__main__":
    main()
