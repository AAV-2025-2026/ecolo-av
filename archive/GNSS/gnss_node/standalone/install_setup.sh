#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "ZED-F9R GPS One-Time Setup"
echo "This script requires sudo privileges to install packages and set udev rules."
echo "Please answer the prompt to enter your password."

# 1. Install Dependencies
echo "Installing system packages (rtklib, python3-serial, python3-pynmea2)..."
sudo apt-get update
sudo apt-get install -y rtklib python3-serial python3-nmea2

# 2. Setup Udev Rules for u-blox ZED-F9R
UDEV_FILE="/etc/udev/rules.d/99-ublox-gnss.rules"
UDEV_RULE='SUBSYSTEM=="tty", ATTRS{idVendor}=="1546", MODE="0666", SYMLINK+="zed_f9r"'

echo "Configuring udev rules for persistent USB access..."
echo "$UDEV_RULE" | sudo tee "$UDEV_FILE" > /dev/null

# Reload udev so the rules take effect immediately
sudo udevadm control --reload-rules
sudo udevadm trigger

# 3. Verification
echo ""
echo "Reading the newly created udev rule file ($UDEV_FILE):"
echo "--------------------------------------------------------"
cat "$UDEV_FILE"
echo "--------------------------------------------------------"
echo ""

echo "Setup Complete!"
echo "If the module is currently plugged in, please unplug it and plug it back in so the new /dev/zed_f9r symlink is created."
