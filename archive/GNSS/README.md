# ZED-F9R GNSS Node

A lightweight, no-build ROS 2 node for the u-blox **ZED-F9R-01B**.  
This version runs directly as a Python script to run a ROS2 GNSS node as well as recieve RTK corrections

## Architecture

This uses a **Sidecar Architecture** designed for high stability:

```text
[ Internet ] 
     |
     v (NTRIP)
[ str2str ]  <-- Runs in Terminal 1
     |
     v (TCP :4000)
[ gnss_node.py ]  <-----> [ /dev/ttyACM0 ]
     |  (Reads NMEA)         (Writes RTCM3)
     |
     v
[ ROS 2 Topic: /gps/fix ]
```

## Prerequisites

### 1. Install Dependencies

    sudo apt update
    sudo apt install -y rtklib python3-pip python3-serial
    pip3 install -r requirements.txt

### 2. Grant Serial Permissions

    sudo usermod -a -G dialout $USER

IMPORTANT: Log out and log back in (or restart) for this change to take effect.

## Installation

### 1. Setup Files

Place the following files in a folder (e.g., ~/my_gps_node/):

- gnss_self_test.py
- gnss_node.py
- start_gps.sh
- requirements.txt

### 2. Make Executable

    chmod +x *.py *.sh

## Usage

### Step 1: Configure credentials (edit start_gps.sh)

    EMAIL="your_email@example.com"
    MOUNTPOINT="CanalTerris"
    SERIAL_PORT="/dev/ttyACM0"
    FRAME_ID="gps_link"

### Step 2: Run the node

    ./start_gps.sh

### Step 3: Stop

Press Ctrl+C to stop; background RTK processes are cleaned up automatically.

## Configuration

| Variable    | Description            | Default                |
|-------------|------------------------|------------------------|
| EMAIL       | Email used for rtk2go  | your_email@example.com |
| MOUNTPOINT  | RTK stream             | CanalTerris            |
| SERIAL_PORT | ZED-F9R device path    | /dev/ttyACM0           |
| FRAME_ID    | Coordinate system used | gps_link               |

Internal node settings can be changed inside gnss_node.py.

## Topics

| Topic    | Type                  | Description                        |
|----------|-----------------------|------------------------------------|
| /gps/fix | sensor_msgs/NavSatFix | GNSS fix; status 0=Standard, 2=RTK |

## Troubleshooting

### 1. “Permission denied: /dev/ttyACM0”

Cause: User missing dialout group.  
Fix: Run the usermod command and reboot.

### 2. Node exits immediately (Self-Test Failed)

Cause: Weak or unstable GPS signal.  
Fix:

- Ensure clear sky view
- Wait for at least 6 satellites
- Ensure HDOP < 5.0

### 3. “Connection refused” (RTK)

Cause: Cannot connect to local str2str stream.  
Fix:

- Check internet connection
- Verify EMAIL / MOUNTPOINT
- Ensure mountpoint is online at rtk2go.com

## Author

Tommy Csete - Localization Group
