from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package="aav_uart_bridge",
            executable="ackermann_uart_bridge",
            name="ackermann_uart_bridge",
            output="screen",
            parameters=[
                # Edit these as needed:
                {"input_topic": "/ackermann_cmd"},
                {"input_is_stamped": True},
                {"uart_port": "/dev/serial0"},
                {"uart_baud": 115200},
                {"tx_rate_hz": 50.0},
                {"timeout_ms": 250},

                # Safety defaults (turn on once verified):
                {"start_estop": True},
                {"start_armed": False},

                # Steering mapping:
                {"steer_in_is_rad": True},
                {"steer_max_rad": 0.45},
                {"steer_cmd_max": 2000.0},

                # Throttle/brake scaling:
                {"accel_to_throttle": 1.0},
                {"accel_to_brake": 1.0},
                {"throttle_max": 250},
                {"brake_max": 4095},
            ],
        )
    ])
