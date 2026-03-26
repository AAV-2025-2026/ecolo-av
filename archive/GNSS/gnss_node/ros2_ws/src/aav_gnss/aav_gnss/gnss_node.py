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
ROS_TOPIC = '/aav/gps/fix'
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

# Self test and RTK toggles
ENABLE_SELF_TEST_TOGGLE = False
ENABLE_RTK_TOGGLE = False


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
        self.get_logger().debug("GNSSPublisher node initialized")

        # Load ROS parameters
        self.declare_parameter('port', DEFAULT_PORT)
        self.declare_parameter('baud', DEFAULT_BAUD)
        self.declare_parameter('rtk_port', DEFAULT_RTK_PORT)
        self.declare_parameter('frame_id', DEFAULT_FRAME_ID)
        self.declare_parameter('enable_self_test', ENABLE_SELF_TEST_TOGGLE)
        self.declare_parameter('enable_rtk', ENABLE_RTK_TOGGLE)
        self.get_logger().debug("ROS parameters declared")

        self.port = self.get_parameter('port').value
        self.baud = self.get_parameter('baud').value
        self.rtk_port = self.get_parameter('rtk_port').value
        self.frame_id = self.get_parameter('frame_id').value
        self.enable_self_test = self.get_parameter('enable_self_test').value
        self.enable_rtk = self.get_parameter('enable_rtk').value

        self.get_logger().info(f"Parameters loaded: port={self.port}, baud={self.baud}, rtk_port={self.rtk_port}, frame_id={self.frame_id}, enable_self_test={self.enable_self_test}, enable_rtk={self.enable_rtk}")

        # THREAD SAFETY NOTE: We rely on PySerial's native POSIX thread-safety for concurrent Rx/Tx
        # instead of a manual lock. This prevents the NMEA reader from blocking the RTK stream.
        self.get_logger().debug("Concurrent Rx/Tx enabled (Lock-free)")

        # Default Covariance
        self.lat_var = ACCURACY_UNKNOWN
        self.lon_var = ACCURACY_UNKNOWN
        self.alt_var = ACCURACY_UNKNOWN
        self.get_logger().debug("Default variances set to unknown")

        # Self-Test: Verify GPS is responsive before proceeding (if enabled)
        if self.enable_self_test:
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
        else:
            self.get_logger().info("Self-Test disabled, proceeding without hardware verification")

        # Establish Serial Connection
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=SERIAL_TIMEOUT_READ)
            self.get_logger().info(f"Connected to GNSS Receiver on {self.port}")
            self.get_logger().debug("Serial connection established successfully")

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

        # Launch RTK background listener (if enabled)
        if self.enable_rtk:
            self.rtk_thread = threading.Thread(target=self.rtk_worker, daemon=True)
            self.rtk_thread.start()
            self.get_logger().debug("RTK worker thread started")
        else:
            self.rtk_thread = None
            self.get_logger().info("RTK stream disabled")

        # Start Main Publishing Timer
        self.pub = self.create_publisher(NavSatFix, ROS_TOPIC, QUEUE_SIZE)
        self.create_timer(PUBLISH_RATE, self.read_gps)
        self.get_logger().debug("Publishing timer created")

    def rtk_worker(self):
        """
        Background thread for RTCM injection.

        Connects to a local TCP stream (e.g., str2str) and forwards any received
        correction data directly to the GNSS receiver via the serial port.
        """
        self.get_logger().debug("RTK worker thread entered")
        while rclpy.ok():
            self.get_logger().debug("RTK worker attempting connection")
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(RTK_CONN_TIMEOUT)
                    self.get_logger().debug("RTK socket created and timeout set")
                    try:
                        s.connect((RTK_HOST, self.rtk_port))
                        self.get_logger().info(f"Connected to RTK Stream ({RTK_HOST}:{self.rtk_port})")
                        self.get_logger().debug("RTK socket connected successfully")

                        while rclpy.ok():
                            try:
                                data = s.recv(RTK_BUFFER_SIZE)
                                self.get_logger().debug(f"Received {len(data)} bytes from RTK stream")
                                if not data:
                                    self.get_logger().warning("RTK Stream closed by server.")
                                    break

                                # THREAD SAFETY: PySerial natively handles concurrent Tx writes.
                                # No lock needed here, preventing bottlenecks with the Rx thread.
                                if self.ser and self.ser.is_open:
                                    try:
                                        self.ser.write(data)
                                        self.get_logger().debug("RTK data written to serial port")
                                    except serial.SerialException as e:
                                        self.get_logger().error(f"Hardware disconnect during RTK write: {e}")
                                        break # Drop connection, let hardware recover

                            except socket.timeout:
                                # Normal if no data is sent for a while, just loop
                                self.get_logger().debug("RTK socket timeout")
                                continue
                            except OSError as e:
                                self.get_logger().error(f"RTK Socket Error during receive: {e}")
                                break

                    except (ConnectionRefusedError, socket.timeout):
                        # Expected behavior if str2str hasn't started yet
                        self.get_logger().debug("RTK connection refused or timed out")
                        pass
                    except OSError as e:
                        self.get_logger().warning(f"Could not connect to RTK server: {e}")

            except Exception as e:
                self.get_logger().error(f"Unexpected RTK Worker Error: {e}")

            # Wait before attempting reconnection
            self.get_logger().debug("RTK worker sleeping before retry")
            time.sleep(RTK_RETRY_DELAY)

    def read_gps(self):
        """
        Timer callback that polls the serial port for new NMEA lines.

        Uses a while loop to drain the serial buffer completely. This ensures
        that bursts of messages (which occur at 10Hz) are processed immediately
        instead of building up latency.
        """
        self.get_logger().debug("read_gps timer callback triggered")
        
        # THREAD SAFETY: PySerial natively handles concurrent Rx reads.
        if not self.ser or not self.ser.is_open:
            self.get_logger().debug("Serial port not available, skipping read")
            return

        try:
            # Loop while data is waiting in the buffer (Fix for 10Hz latency)
            while self.ser.in_waiting:
                raw_line = self.ser.readline()
                # errors='replace' prevents UnicodeDecodeError, so no try/except needed here
                line = raw_line.decode('utf-8', errors='replace').strip()
                self.get_logger().debug(f"Read NMEA line: {line}")

                if line.startswith(NMEA_HEADERS_ERR):
                    self.get_logger().debug("Processing GST message")
                    self.process_gst(line)
                elif line.startswith(NMEA_HEADERS_POS):
                    self.get_logger().debug("Processing GGA message")
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
        self.get_logger().debug(f"Parsing GST message: {line}")
        try:
            msg = pynmea2.parse(line)
            self.get_logger().debug("GST message parsed successfully")

            # Extract Standard Deviations (in meters)
            # Explicit float() conversion ensures ValueError if fields are empty
            lat_sigma = float(msg.std_dev_latitude)
            lon_sigma = float(msg.std_dev_longitude)
            alt_sigma = float(msg.std_dev_altitude)
            self.get_logger().debug(f"Extracted sigmas: lat={lat_sigma}, lon={lon_sigma}, alt={alt_sigma}")

            self.lat_var = lat_sigma ** 2
            self.lon_var = lon_sigma ** 2
            self.alt_var = alt_sigma ** 2

            self.get_logger().info(f"Variance updated: lat={self.lat_var:.2f}, lon={self.lon_var:.2f}, alt={self.alt_var:.2f}")

        except (ValueError, TypeError, pynmea2.ParseError, AttributeError):
            # Reset to unknown if data is unreliable
            self.lat_var = ACCURACY_UNKNOWN
            self.lon_var = ACCURACY_UNKNOWN
            self.alt_var = ACCURACY_UNKNOWN
            self.get_logger().warning("GST message malformed or incomplete, resetting variances to unknown")

    def publish_fix(self, line):
        """
        Parses GGA messages and publishes the ROS 2 NavSatFix message.

        Handles:
        - Timestamp synchronization (GPS UTC -> ROS Time)
        - Altitude conversion (MSL + GeoSep -> Ellipsoid)
        - Mapping NMEA quality flags to ROS NavSatStatus
        - Populating covariance matrix from most recent GST data
        """
        self.get_logger().debug(f"Parsing GGA message: {line}")
        try:
            msg = pynmea2.parse(line)
            self.get_logger().debug("GGA message parsed successfully")
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
                self.get_logger().debug("Used fallback timestamp")

            fix.header.frame_id = self.frame_id
            self.get_logger().debug(f"Header set: frame_id={fix.header.frame_id}")

            # --- ALTITUDE CORRECTION ---
            # NavSatFix expects WGS84 Ellipsoidal Height.
            # NMEA provides MSL Altitude. We add Geoidal Separation to convert.
            msl_alt = float(msg.altitude or 0.0)
            geo_sep = float(msg.geo_sep or 0.0)
            fix.altitude = msl_alt + geo_sep
            self.get_logger().debug(f"Altitude calculated: MSL={msl_alt}, GeoSep={geo_sep}, Ellipsoid={fix.altitude}")

            # Use 'or 0.0' to handle empty strings if GPS loses lock but sends headers
            fix.latitude = float(msg.latitude or 0.0)
            fix.longitude = float(msg.longitude or 0.0)
            self.get_logger().debug(f"Position set: lat={fix.latitude}, lon={fix.longitude}")

            # --- STATUS MAPPING ---
            qual = int(msg.gps_qual)
            self.get_logger().debug(f"GPS quality: {qual}")

            if qual in [4, 5]:
                fix.status.status = NavSatStatus.STATUS_GBAS_FIX
            elif qual == 2:
                fix.status.status = NavSatStatus.STATUS_SBAS_FIX
            elif qual in [1, 3, 6]:
                fix.status.status = NavSatStatus.STATUS_FIX
            else:
                fix.status.status = NavSatStatus.STATUS_NO_FIX

            self.get_logger().debug(f"Status set to {fix.status.status}")

            # --- COVARIANCE ---
            fix.position_covariance = [
                self.lat_var, 0.0, 0.0,
                0.0, self.lon_var, 0.0,
                0.0, 0.0, self.alt_var
            ]
            fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN
            self.get_logger().debug(f"Covariance set: {fix.position_covariance}")

            self.pub.publish(fix)
            self.get_logger().debug("NavSatFix message published")

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
        self.get_logger().debug("Cleanup method called")
        if hasattr(self, 'ser') and self.ser:
            try:
                self.ser.close()
                self.get_logger().debug("Serial port closed")
            except Exception as e:
                self.get_logger().error(f"Error closing serial port: {e}")
            finally:
                self.ser = None
                self.get_logger().info("Closed serial connection.")
        else:
            self.get_logger().debug("No serial port to close")


def main(args=None):
    """
    Main entry point. Initializes the ROS node, spins the event loop,
    and catches top-level exceptions.
    """
    rclpy.init(args=args)
    node = GNSSPublisher()
    try:
        node.get_logger().info("GNSS Node started successfully")
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
