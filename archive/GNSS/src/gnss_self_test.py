#!/usr/bin/env python3
"""
GNSS Self-Test Module
---------------------
Provides a blocking check to ensure the GPS receiver has a valid signal
before the main driver operation begins.
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


def check_gps_ready(logger, serial_port, baud_rate, timeout_seconds):
    """
    Performs a blocking self-test on the GNSS receiver.
    Args:
        logger: ROS 2 logger instance.
        serial_port (str): Path to the serial port.
        baud_rate (int): Baud rate for the connection.
        timeout_seconds (int): Max time to wait for a pass.
    Returns:
        bool: True if the test passed, False if it timed out.
    """
    logger.info(f"--- Starting Self-Test on {serial_port} ---")

    start_time = time.time()
    consecutive_good_fixes = 0

    try:
        with serial.Serial(serial_port, baud_rate, timeout=SERIAL_READ_TIMEOUT) as ser:
            # Loop while ROS is okay AND we haven't timed out
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
                        logger.warn(
                            f"Waiting for stronger signal... "
                            f"(Sats={sats}/{MIN_SATELLITES}, "
                            f"HDOP={hdop}/{MAX_HDOP_THRESHOLD}, Qual={qual})"
                        )
                        consecutive_good_fixes = 0

                    if consecutive_good_fixes >= REQUIRED_CONSECUTIVE_FIXES:
                        logger.info("SELF-TEST PASSED. GPS is ready.")
                        return True

                except pynmea2.ParseError as e:
                    logger.warn(f"Failed to parse NMEA sentence: {e}")
                    continue
                except ValueError:
                    logger.warn("Received malformed numerical data in NMEA string.")
                    continue
                except Exception as e:
                    logger.error(f"Error reading from GNSS sensor: {e}")
                    continue

        logger.error("Self-Test Timed Out.")
        return False

    except serial.SerialException as e:
        logger.fatal(f"Self-Test Connection Error (Port Access): {e}")
        return False
    except Exception as e:
        logger.fatal(f"Self-Test Unexpected Error: {e}")
        return False
