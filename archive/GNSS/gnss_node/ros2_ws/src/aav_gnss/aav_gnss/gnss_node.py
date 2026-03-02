#!/usr/bin/env python3
"""
GNSS Node
-------------------------
A thread-safe, configurable ROS 2 publisher for the u-blox ZED-F9R GNSS receiver.
It handles serial communication, NTRIP/RTK correction injection, and parsing of
NMEA datasets into standard ROS `NavSatFix` messages with covariance estimates.
"""

import sys
import socket
import threading
import time
import serial
import pynmea2
import datetime
from datetime import timezone

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, NavSatStatus

from aav_gnss import gnss_self_test

# --- CONFIGURATION CONSTANTS ---

# Serial Defaults
DEFAULT_PORT = '/dev/zed_f9r'
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
NMEA_HEADERS_POS = ('$GNGGA', '$GPGGA')
NMEA_HEADERS_ERR = ('$GNGST', '$GPGST')

# Fallback Variance
# Used when GST data is missing or invalid.
# 1e9 = ~31km standard deviation
ACCURACY_UNKNOWN = 1e9


class GNSSPublisher(Node):
    """
    ROS 2 Node for the u-blox ZED-F9R.

    This node operates two main concurrent processes:
    1. A background thread that pipes RTCM corrections from a TCP socket to the serial port.
    2. A main timer loop that polls the serial port for NMEA data and publishes to ROS.
    """

    def __init__(self):
        """
        Initializes parameters, performs hardware self-tests, establishes
        serial connections, and starts the RTK worker thread.
        """
        super().__init__('gnss_node')

        # Load ROS parameters
        self.declare_parameter('port', DEFAULT_PORT)
        self.declare_parameter('baud', DEFAULT_BAUD)
        self.declare_parameter('rtk_port', DEFAULT_RTK_PORT)
        self.declare_parameter('frame_id', DEFAULT_FRAME_ID)

        self.port = self.get_parameter('port').value
        self.baud = self.get_parameter('baud').value
        self.rtk_port = self.get_parameter('rtk_port').value
        self.frame_id = self.get_parameter('frame_id').value

        # Thread lock is strictly required because 'rtk_worker' writes to serial
        # while 'read_gps' reads from serial.
        self.serial_lock = threading.Lock()

        # Initialize Default Covariance (using Fallback number logic)
        self.lat_var = ACCURACY_UNKNOWN
        self.lon_var = ACCURACY_UNKNOWN
        self.alt_var = ACCURACY_UNKNOWN

        # Perform Blocking Self-Test
        try:
            test_passed = gnss_self_test.check_gps_ready(
                self.get_logger(),
                self.port,
                self.baud,
                SELF_TEST_TIMEOUT
            )
        except Exception as e:
            self.get_logger().fatal(f"Self-Test crashed with unexpected error: {e}")
            sys.exit(1)

        if not test_passed:
            self.get_logger().fatal("Self-Test Failed. Exiting to prevent unsafe operation.")
            sys.exit(1)

        # Establish Serial Connection
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=SERIAL_TIMEOUT_READ)
            self.get_logger().info(f"Connected to GNSS Receiver on {self.port}")

        except serial.SerialException as e:
            if "Permission denied" in str(e):
                self.get_logger().fatal(f"PERMISSION DENIED: Could not open {self.port}. "
                                        f"Try running: sudo usermod -aG dialout $USER")
            elif "No such file" in str(e):
                self.get_logger().fatal(f"DEVICE NOT FOUND: {self.port} does not exist. "
                                        f"Is the GPS plugged in?")
            else:
                self.get_logger().fatal(f"Serial Connection Error: {e}")
            sys.exit(1)

        # Launch RTK background listener
        self.rtk_thread = threading.Thread(target=self.rtk_worker, daemon=True)
        self.rtk_thread.start()

        # Start Main Publishing Timer
        self.pub = self.create_publisher(NavSatFix, ROS_TOPIC, QUEUE_SIZE)
        self.create_timer(PUBLISH_RATE, self.read_gps)

    def rtk_worker(self):
        """
        Background thread for RTCM injection.

        Connects to a local TCP stream (e.g., str2str) and forwards any received
        correction data directly to the GNSS receiver via the serial port.
        """
        while rclpy.ok():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(RTK_CONN_TIMEOUT)
                    try:
                        s.connect((RTK_HOST, self.rtk_port))
                        self.get_logger().info(f"Connected to RTK Stream ({RTK_HOST}:{self.rtk_port})")

                        while rclpy.ok():
                            try:
                                data = s.recv(RTK_BUFFER_SIZE)
                                if not data:
                                    self.get_logger().warning("RTK Stream closed by server.")
                                    break

                                # THREAD SAFETY: Acquire lock before writing
                                with self.serial_lock:
                                    if self.ser and self.ser.is_open:
                                        self.ser.write(data)

                            except socket.timeout:
                                # Normal if no data is sent for a while, just loop
                                continue
                            except OSError as e:
                                self.get_logger().error(f"RTK Socket Error during receive: {e}")
                                break

                    except (ConnectionRefusedError, socket.timeout):
                        # Expected behavior if str2str hasn't started yet
                        pass
                    except OSError as e:
                        self.get_logger().warning(f"Could not connect to RTK server: {e}")

            except Exception as e:
                self.get_logger().error(f"Unexpected RTK Worker Error: {e}")

            # Wait before attempting reconnection
            time.sleep(RTK_RETRY_DELAY)

    def read_gps(self):
        """
        Timer callback that polls the serial port for new NMEA lines.

        Uses a while loop to drain the serial buffer completely. This ensures
        that bursts of messages (which occur at 10Hz) are processed immediately
        instead of building up latency.
        """
        # THREAD SAFETY: Acquire lock before reading
        with self.serial_lock:
            if not self.ser or not self.ser.is_open:
                return

            try:
                # Loop while data is waiting in the buffer (Fix for 10Hz latency)
                while self.ser.in_waiting:
                    raw_line = self.ser.readline()
                    # errors='replace' prevents UnicodeDecodeError, so no try/except needed here
                    line = raw_line.decode('utf-8', errors='replace').strip()

                    if line.startswith(NMEA_HEADERS_ERR):
                        self.process_gst(line)
                    elif line.startswith(NMEA_HEADERS_POS):
                        self.publish_fix(line)

            except serial.SerialException as e:
                self.get_logger().error(f"Serial Read Error (Device disconnected?): {e}")
            except UnicodeError as e:
                # Fallback for very malformed data not caught by replace
                self.get_logger().warning(f"Unicode Error ignored: {e}")
            except Exception as e:
                self.get_logger().error(f"Unexpected error in read_gps: {e}")

    def process_gst(self, line):
        """
        Parses GST (Pseudorange Error Statistics) messages to update covariance.

        Calculates variance from standard deviation (Var = Sigma^2).
        If the message is malformed or fields are empty, resets variance to
        ACCURACY_UNKNOWN to prevent high-confidence reporting on stale data.
        """
        try:
            msg = pynmea2.parse(line)

            # Extract Standard Deviations (in meters)
            # Explicit float() conversion ensures ValueError if fields are empty
            lat_sigma = float(msg.std_dev_latitude)
            lon_sigma = float(msg.std_dev_longitude)
            alt_sigma = float(msg.std_dev_altitude)

            self.lat_var = lat_sigma ** 2
            self.lon_var = lon_sigma ** 2
            self.alt_var = alt_sigma ** 2

        except (ValueError, TypeError, pynmea2.ParseError, AttributeError):
            # Reset to unknown if data is unreliable
            self.lat_var = ACCURACY_UNKNOWN
            self.lon_var = ACCURACY_UNKNOWN
            self.alt_var = ACCURACY_UNKNOWN

    def publish_fix(self, line):
        """
        Parses GGA messages and publishes the ROS 2 NavSatFix message.

        Handles:
        - Timestamp synchronization (GPS UTC -> ROS Time)
        - Altitude conversion (MSL + GeoSep -> Ellipsoid)
        - Mapping NMEA quality flags to ROS NavSatStatus
        - Populating covariance matrix from most recent GST data
        """
        try:
            msg = pynmea2.parse(line)
            fix = NavSatFix()

            # --- TIMESTAMP LOGIC ---
            try:
                today = datetime.datetime.now(timezone.utc).date()
                if msg.timestamp:
                    gps_dt = datetime.datetime.combine(today, msg.timestamp)
                    unix_timestamp = gps_dt.replace(tzinfo=timezone.utc).timestamp()
                    fix.header.stamp = rclpy.time.Time(seconds=unix_timestamp).to_msg()
                else:
                    raise ValueError("No timestamp in message")
            except (ValueError, Exception):
                # Critical fallback if GPS time is invalid/missing
                fix.header.stamp = self.get_clock().now().to_msg()

            fix.header.frame_id = self.frame_id

            # --- ALTITUDE CORRECTION ---
            # NavSatFix expects WGS84 Ellipsoidal Height.
            # NMEA provides MSL Altitude. We add Geoidal Separation to convert.
            msl_alt = float(msg.altitude or 0.0)
            geo_sep = float(msg.geo_sep or 0.0)
            fix.altitude = msl_alt + geo_sep

            # Use 'or 0.0' to handle empty strings if GPS loses lock but sends headers
            fix.latitude = float(msg.latitude or 0.0)
            fix.longitude = float(msg.longitude or 0.0)

            # --- STATUS MAPPING ---
            qual = int(msg.gps_qual)

            if qual in [4, 5]:
                fix.status.status = NavSatStatus.STATUS_GBAS_FIX
            elif qual == 2:
                fix.status.status = NavSatStatus.STATUS_SBAS_FIX
            elif qual in [1, 3, 6]:
                fix.status.status = NavSatStatus.STATUS_FIX
            else:
                fix.status.status = NavSatStatus.STATUS_NO_FIX

            # --- COVARIANCE ---
            fix.position_covariance = [
                self.lat_var, 0.0, 0.0,
                0.0, self.lon_var, 0.0,
                0.0, 0.0, self.alt_var
            ]
            fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN

            self.pub.publish(fix)

            self.get_logger().info(
                f"GNSS: Lat {fix.latitude:.6f}, Lon {fix.longitude:.6f}, "
                f"Qual {qual} (Err={self.lat_var ** 0.5:.3f}m)"
            )

        except ValueError as e:
            self.get_logger().warning(f"Incomplete NMEA data (missing fields): {e}")
        except pynmea2.ParseError as e:
            self.get_logger().warning(f"Failed to parse NMEA checksum: {e}")
        except Exception as e:
            self.get_logger().error(f"Critical error publishing fix: {e}")

    def cleanup(self):
        """
        Gracefully closes the serial connection on node shutdown.
        """
        with self.serial_lock:
            if hasattr(self, 'ser') and self.ser:
                try:
                    self.ser.close()
                except Exception as e:
                    self.get_logger().error(f"Error closing serial port: {e}")
                finally:
                    self.ser = None
                    self.get_logger().info("Closed serial connection.")


def main(args=None):
    """
    Main entry point. Initializes the ROS node, spins the event loop,
    and catches top-level exceptions.
    """
    rclpy.init(args=args)
    node = GNSSPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Node crashed with fatal error: {e}")
    finally:
        node.cleanup()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
