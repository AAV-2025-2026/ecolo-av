#!/usr/bin/env python3
"""
ZED-F9R-01B ROS 2 Node
-------------------------
Thread-safe, configurable Node for u-blox ZED-F9R.
Handles self-testing, RTK injection, and publishes NavSatFix messages
with correct WGS 84 altitude conversions.
"""

import sys
import socket
import threading
import time
import serial
import pynmea2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, NavSatStatus

import gnss_self_test

# --- CONFIGURATION CONSTANTS ---

# Serial Defaults
DEFAULT_PORT = '/dev/ttyACM0'
DEFAULT_BAUD = 115200
SERIAL_TIMEOUT_READ = 0.1  # Seconds

# RTK / NTRIP Settings
DEFAULT_RTK_PORT = 4000
RTK_HOST = '127.0.0.1'  # Localhost (str2str is running locally)
RTK_CONN_TIMEOUT = 5  # Seconds to wait for socket connection
RTK_RETRY_DELAY = 5  # Seconds to wait before retrying connection
RTK_BUFFER_SIZE = 2048  # Bytes to read from TCP stream

# ROS Publishing Settings
ROS_TOPIC = '/gps/fix'
DEFAULT_FRAME_ID = 'gps_link'
PUBLISH_RATE = 0.1  # Timer period in seconds (0.1s = 10Hz)
QUEUE_SIZE = 10
SELF_TEST_TIMEOUT = 30  # Seconds

# NMEA Parsing
NMEA_HEADERS = ('$GNGGA', '$GPGGA')

# GNSS Accuracy Estimates (Standard Deviation in Meters)
# used to calculate covariance: Variance = (HDOP * Base_Accuracy)^2
ACCURACY_RTK_FIXED = 0.01  # ~1cm
ACCURACY_RTK_FLOAT = 0.05  # ~5cm
ACCURACY_DGPS = 1.0  # ~1m
ACCURACY_STANDARD = 2.5  # ~2.5m
ACCURACY_UNKNOWN = 5.0  # Fallback


class GNSSPublisher(Node):
    """
    ROS 2 Node for the u-blox ZED-F9R with RTK support.
    """

    def __init__(self):
        """
        Initialize the node, parameters, self-test, and connections.
        """
        super().__init__('gnss_node')

        # 1. Configuration Parameters
        self.declare_parameter('port', DEFAULT_PORT)
        self.declare_parameter('baud', DEFAULT_BAUD)
        self.declare_parameter('rtk_port', DEFAULT_RTK_PORT)
        self.declare_parameter('frame_id', DEFAULT_FRAME_ID)

        self.port = self.get_parameter('port').value
        self.baud = self.get_parameter('baud').value
        self.rtk_port = self.get_parameter('rtk_port').value
        self.frame_id = self.get_parameter('frame_id').value

        # Initialize the thread lock for the serial port
        self.serial_lock = threading.Lock()

        # 2. Run Self-Test (Blocking)
        # Note: Self-test creates its own local serial connection.
        test_passed = gnss_self_test.check_gps_ready(
            self.get_logger(),
            self.port,
            self.baud,
            SELF_TEST_TIMEOUT
        )

        if not test_passed:
            self.get_logger().fatal("Self-Test Failed. Exiting.")
            sys.exit(1)

        # 3. Connect to Hardware
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=SERIAL_TIMEOUT_READ)
            self.get_logger().info(f"Connected to {self.port}")
        except Exception as e:
            self.get_logger().fatal(f"Could not open serial: {e}")
            sys.exit(1)

        # 4. Start RTK Listener (Background Thread)
        self.rtk_thread = threading.Thread(target=self.rtk_worker, daemon=True)
        self.rtk_thread.start()

        # 5. Start Publisher Timer
        self.pub = self.create_publisher(NavSatFix, ROS_TOPIC, QUEUE_SIZE)
        self.create_timer(PUBLISH_RATE, self.read_gps)

    def rtk_worker(self):
        """
        Background thread that connects to the local str2str instance
        and injects RTCM corrections into the GPS serial port.
        """
        while rclpy.ok():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(RTK_CONN_TIMEOUT)
                    s.connect((RTK_HOST, self.rtk_port))
                    self.get_logger().info(f"Connected to RTK Stream ({RTK_HOST}:{self.rtk_port})")

                    while rclpy.ok():
                        data = s.recv(RTK_BUFFER_SIZE)
                        if not data:
                            break

                        # THREAD SAFETY: Acquire lock before writing
                        with self.serial_lock:
                            if self.ser and self.ser.is_open:
                                self.ser.write(data)

            except Exception:
                # Wait and retry if str2str isn't running
                time.sleep(RTK_RETRY_DELAY)

    def read_gps(self):
        """
        Timer callback to read raw NMEA data from the serial port.
        """
        # THREAD SAFETY: Acquire lock before reading
        with self.serial_lock:
            if not self.ser or not self.ser.is_open:
                return

            if self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line.startswith(NMEA_HEADERS):
                        self.publish_fix(line)
                except Exception:
                    pass

    def publish_fix(self, line):
        """
        Parses the NMEA line and publishes a ROS 2 NavSatFix message.
        Includes altitude correction (MSL -> WGS84) and covariance estimation.
        """
        try:
            msg = pynmea2.parse(line)
            fix = NavSatFix()
            fix.header.stamp = self.get_clock().now().to_msg()
            fix.header.frame_id = self.frame_id
            fix.latitude = float(msg.latitude)
            fix.longitude = float(msg.longitude)

            # Just passes the raw MSL altitude from the NMEA string
            fix.altitude = float(msg.altitude)

            # --- STATUS MAPPING ---
            qual = int(msg.gps_qual)

            # Map NMEA Quality to ROS Status
            if qual in [4, 5]:
                fix.status.status = NavSatStatus.STATUS_GBAS_FIX
            elif qual == 2:
                fix.status.status = NavSatStatus.STATUS_SBAS_FIX
            elif qual in [1, 3, 6]:
                fix.status.status = NavSatStatus.STATUS_FIX
            else:
                fix.status.status = NavSatStatus.STATUS_NO_FIX

            # --- COVARIANCE CALCULATION ---
            # 1. Get HDOP
            try:
                hdop = float(msg.horizontal_dil)
            except (ValueError, AttributeError, TypeError):
                hdop = 1.0

            # 2. Determine Base Accuracy
            base_accuracy = ACCURACY_UNKNOWN

            if qual == 4:  # RTK Fixed
                base_accuracy = ACCURACY_RTK_FIXED
            elif qual == 5:  # RTK Float
                base_accuracy = ACCURACY_RTK_FLOAT
            elif qual == 2:  # DGPS
                base_accuracy = ACCURACY_DGPS
            elif qual in [1, 3, 6]:  # Standard
                base_accuracy = ACCURACY_STANDARD

            # 3. Calculate Variance
            variance = (hdop * base_accuracy) ** 2

            # 4. Populate Covariance Matrix
            fix.position_covariance = [
                variance, 0.0, 0.0,
                0.0, variance, 0.0,
                0.0, 0.0, variance * 4.0
            ]
            fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_APPROXIMATED

            self.pub.publish(fix)

            self.get_logger().info(
                f"Published GNSS: Lat {fix.latitude:.6f}, Lon {fix.longitude:.6f}, "
                f"Alt {fix.altitude:.2f}m, Qual {qual} (HDOP={hdop})"
            )

        except pynmea2.ParseError as e:
            self.get_logger().warn(f"Failed to parse NMEA sentence: {e}")
        except Exception as e:
            self.get_logger().error(f"Error reading from GNSS sensor: {e}")

    def cleanup(self):
        """
        Closes the serial connection gracefully on shutdown.
        """
        with self.serial_lock:
            if self.ser:
                self.ser.close()
                self.ser = None
                self.get_logger().info("Closed serial connection.")


def main(args=None):
    rclpy.init(args=args)
    node = GNSSPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cleanup()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
