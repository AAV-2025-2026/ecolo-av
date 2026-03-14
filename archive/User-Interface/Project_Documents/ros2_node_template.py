#!/usr/bin/env python3

# This file is just a template showing how to implement a ros2 node that either subscribes or publishes to a topic in a ros2 workspace.

import rclpy
from rclpy.node import Node


class SomeNode(Node):

    def __init__(self):
        # add initialization below
        super().__init__("name_of_node")

        # this repeats functions
        self.create_timer(1.0, self.periodic_function)

        # this makes this node a publisher for a specific topic
        self.topic_name_pub_ = self.create_publisher(msg_type, "name_of_topic", 10)

        # this makes this node a subscriber for a specific topic
        self.topic_name_sub_ = self.create_subscription(msg_type, "name_of_topic", callback_function_recieve_msg)



    def periodic_function(self):
        # add repeatable code here
        self.some_value_ = "test"

    # function that sends msg to topic
    def callback_function_send_msg(self):
        msg = msg_type()
        msg.string = "test"
        self.topic_name_pub_.publish(msg)

    # function that receives msg from a topic
    def callback_function_recieve_msg(self, msg: msg_type):
        self.get_logger().info(str(msg))



def main(args=None):
    rclpy.init(args=args)

    node = SomeNode()
    rclpy.spin(node)   # keeps node alive until process termination (like pressing Ctrl+C)

    rclpy.shutdown