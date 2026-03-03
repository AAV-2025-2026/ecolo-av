#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

#   ------ imu imports and settings -----
import smbus
import time
accel_sensitivty_val = 8192
gyro_sensitivity_val = 131

bus = smbus.SMBus(1)    
address = 0x68

# Wake MPU9250
bus.write_byte_data(address, 0x6B, 0)

def read_word(addr):
    high = bus.read_byte_data(address, addr)
    low  = bus.read_byte_data(address, addr+1)
    val  = (high << 8) + low
    if val >= 0x8000:
        val = -((65535 - val) + 1)
    return val



class SomeNode(Node):

    def __init__(self):
        # add initialization below
        super().__init__("sensor_mpu9250_imu_node")

        # this repeats functions
        self.create_timer(0.5, self.callback_function_send_msg)

        # this makes this node a publisher for a specific topic
        self.topic_name_pub_ = self.create_publisher(Imu, "/imu/data", 10)


    def periodic_function(self):
        # add repeatable code here
        self.some_value_ = "test"

    # function that sends msg to topic
    def callback_function_send_msg(self):

        # acceleration
        accel_x = read_word(0x3B) /accel_sensitivty_val
        accel_y = read_word(0x3D) /accel_sensitivty_val
        accel_z = read_word(0x3F) /accel_sensitivty_val

        # gyro
        gyro_x = read_word(0x43) /gyro_sensitivity_val
        gyro_y = read_word(0x45) /gyro_sensitivity_val
        gyro_z = read_word(0x47) /gyro_sensitivity_val


        print(
            f"Accel: {accel_x:.4g} {accel_y:.4g} {accel_z:.4g} "
            f"Gyro: {gyro_x:.4g} {gyro_y:.4g} {gyro_z:.4g}"
        )

        #msg = msg_type()
        #msg.string = "test"
        #self.topic_name_pub_.publish(msg)





def main(args=None):
    rclpy.init(args=args)

    node = SomeNode()
    rclpy.spin(node)   # keeps node alive until termination with Ctrl+C

    rclpy.shutdown