#!/usr/bin/env python3
"""
GNSS Self-Test Module
---------------------
Provides a blocking check to ensure the GPS receiver has a valid signal
before the main publisher operation begins.
"""

import time
import serial
import pynmea2
import rclpy

# --- CONFIGURATION CONSTANTS ---

# Test Pass Criteria
REQUIRED_CONSECUTIVE_FIXES = 5
MAX_HDOP_THRESHOLD = 5.0  # Lower is better
MIN_SATELLITES = 6  # Minimum visible sats
MIN_FIX_QUALITY = 1  # 0=Invalid, 1=GPS, 2=DGPS, 4=RTK, etc.

# Serial & NMEA Settings
SERIAL_READ_TIMEOUT = 1  # Seconds to wait for a single line
NMEA_HEADERS = ('$GNGGA', '$GPGGA')
ENCODING = 'utf-8'

# Retry Settings
RETRY_WAIT_SECONDS = 15  # Time to wait before retrying after failure


def check_gps_ready(logger, serial_port, baud_rate, timeout_seconds):
    """
    Performs a blocking self-test on the GNSS receiver.
    Retries indefinitely until the test passes or ROS shuts down.

    Args:
        logger: ROS 2 logger instance.
        serial_port (str): Path to the serial port.
        baud_rate (int): Baud rate for the connection.
        timeout_seconds (int): Max time to wait for a pass per attempt.
    Returns:
        bool: True if the test passed, False if ROS shutdown triggered exit.
    """

    # Outer loop for Infinite Retries
    while rclpy.ok():
        logger.info(f"--- Starting Self-Test on {serial_port} ---")
        start_time = time.time()
        consecutive_good_fixes = 0
        test_passed = False

        try:
            with serial.Serial(serial_port, baud_rate, timeout=SERIAL_READ_TIMEOUT) as ser:
                # Loop while ROS is ok AND we haven't timed out for this attempt
                while rclpy.ok() and (time.time() - start_time < timeout_seconds):
                    try:
                        line = ser.readline().decode(ENCODING, errors="replace").strip()

                        if not line.startswith(NMEA_HEADERS):
                            continue

                        msg = pynmea2.parse(line)
                        qual = int(msg.gps_qual)
                        hdop = float(msg.horizontal_dil)
                        sats = int(msg.num_sats)

                        # Check against Constants
                        if (qual >= MIN_FIX_QUALITY and
                                hdop < MAX_HDOP_THRESHOLD and
                                sats >= MIN_SATELLITES):

                            consecutive_good_fixes += 1
                            logger.info(
                                f"Self-Test Progress: {consecutive_good_fixes}/{REQUIRED_CONSECUTIVE_FIXES} "
                                f"(HDOP={hdop}, Sats={sats})"
                            )
                        else:
                            logger.warning(
                                f"Waiting for stronger signal... "
                                f"(Sats={sats}/{MIN_SATELLITES}, "
                                f"HDOP={hdop}/{MAX_HDOP_THRESHOLD}, Qual={qual})"
                            )
                            consecutive_good_fixes = 0

                        if consecutive_good_fixes >= REQUIRED_CONSECUTIVE_FIXES:
                            logger.info("SELF-TEST PASSED. GPS is ready.")
                            test_passed = True
                            break

                    except pynmea2.ParseError as e:
                        logger.warning(f"Failed to parse NMEA sentence: {e}")
                        continue
                    except ValueError:
                        logger.warning("Received malformed numerical data in NMEA string.")
                        continue
                    except Exception as e:
                        logger.error(f"Error reading from GNSS sensor: {e}")
                        continue

            # If we broke out of the serial context:
            if test_passed:
                return True

            # If we exhausted the time limit without passing
            logger.error("Self-Test Timed Out.")

        except serial.SerialException as e:
            logger.fatal(f"Self-Test Connection Error (Port Access): {e}")
        except Exception as e:
            logger.fatal(f"Self-Test Unexpected Error: {e}")

        # --- RETRY WAIT LOGIC ---
        # Test failed (Timeout or Exception).
        # Wait 15 seconds before the loop restarts, checking rclpy.ok() so exit is still possible
        logger.warning(f"Retrying Self-Test in {RETRY_WAIT_SECONDS} seconds...")

        for _ in range(RETRY_WAIT_SECONDS):
            if not rclpy.ok():
                return False
            time.sleep(1)

    return False
