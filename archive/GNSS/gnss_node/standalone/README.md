# ROS2 Custom GNSS Node

A lightweight, no-build (prototype) ROS 2 node for the u-blox **ZED-F9R-01B** GNSS module.
This version runs directly as a Python script to provide a robust ROS 2 GNSS node with an auto-recovering background RTK correction manager.

## Architecture

This uses a **Sidecar Architecture** designed for high stability on the AAV. The launch script handles network drops, automatically reconnecting the RTK stream without interrupting the ROS 2 node.

```text
[ Internet (rtk2go) ] 
         |
         v (NTRIP)
[ str2str Auto-Loop ]  <-- Runs in background, auto-recovers on disconnect
         |
         v (TCP :4000 to Serial)
[   gnss_node.py    ]  <-----> [ /dev/zed_f9r ]
         |  (Reads NMEA)         (Writes RTCM3)
         |
         v
[ ROS 2 Topic: /aav/gps/fix ]
```

## Directory Structure

Ensure your files are organized in the following structure before running the setup:

```text
your_project_folder/
├── install_setup.sh
├── launch_gps.sh
└── src/
    ├── gnss_node.py
    └── gnss_self_test.py
```

## One-Time Setup

The setup script handles all system dependencies and creates a persistent, permission-free USB symlink.

### 1. Run the Setup Script
Open a terminal in the root of the project folder and run:

```bash
chmod +x install_setup.sh launch_gps.sh
./install_setup.sh
```

*This will install `rtklib`, `python3-serial`, and `python3-nmea2` via `apt`, and configure the `udev` rules.*

### 2. Trigger the USB Rule
**IMPORTANT:** Once the script finishes, physically **unplug** the ZED-F9R from the computer and **plug it back in**. This triggers the system rule and creates the `/dev/zed_f9r` shortcut.

## Usage

### Step 1: Configure the Launch File
Open `launch_gps.sh` in a text editor and update the core variables:

```bash
EMAIL="your_email@example.com"
MOUNTPOINT="CanalTerris"
SERIAL_PORT="/dev/zed_f9r"
FRAME_ID="gps"
PROJECT_DIR="/home/your_username/your_project_folder" # Must be absolute, do not use ~
```

### Step 2: Run the Stack
Run the launch script. You do not need `sudo`.

```bash
./launch_gps.sh
```

The ROS 2 node will start publishing immediately (falling back to standard GPS or SBAS). In the background, the script will ping `8.8.8.8` to wait for an internet connection before silently launching the RTK stream. 

### Step 3: Stop
Press **`Ctrl+C`** to safely stop the stack. The cleanup function will automatically kill the Python node background RTK processes to release the serial port.

## Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| **`EMAIL`** | Email used to authenticate with rtk2go | `your_email@example.com` |
| **`MOUNTPOINT`** | The specific RTK stream to pull | `CanalTerris` |
| **`SERIAL_PORT`** | Persistent udev symlink for the ZED-F9R | `/dev/zed_f9r` |
| **`FRAME_ID`** | ROS 2 tf coordinate frame name | `gps` |
| **`PROJECT_DIR`**| Absolute path to the folder containing `src/` | *Requires user input* |

*Internal node settings (like publishing frequency or baud rate) can be changed directly inside `src/gnss_node.py`.*

## Topics

| Topic | Type | Description |
| :--- | :--- | :--- |
| `/aav/gps/fix` | `sensor_msgs/NavSatFix` | Current GNSS fix. See status map below. |

**Status Indicator Mapping:**
* **`-1`**: No Fix (Invalid / Searching)
* **`0`**: Standard GPS / Dead Reckoning
* **`1`**: SBAS (WAAS corrections, default state before RTK connects)
* **`2`**: GBAS / RTK (RTK Float or RTK Fixed)

## Troubleshooting

### 1. "No such file or directory: '/dev/zed_f9r'"
* **Cause:** The `udev` rule hasn't been applied or triggered.
* **Fix:** Ensure you ran `./install_setup.sh`. Unplug the USB cable and plug it back in. Verify it exists by running `ls -l /dev/zed_f9r`.

### 2. "Project directory not found. Exiting."
* **Cause:** The `PROJECT_DIR` in the launch script is misconfigured.
* **Fix:** Ensure the path is absolute (e.g., `/home/username/gnss_project`). Do not use the tilde (`~`) shortcut. Also, ensure the file does not have hidden Windows line endings (run `sed -i 's/\r$//' launch_gps.sh`).

### 3. Node exits immediately (Self-Test Failed)
* **Cause:** Weak or unstable GNSS signal preventing initial lock.
* **Fix:**
  * Ensure the antenna has a clear view of the sky.
  * Wait a few moments for the receiver to acquire at least 6 satellites.
  * Ensure HDOP drops below 5.0.

### 4. RTK loop is stuck on "Waiting for internet connection..."
* **Cause:** The script cannot reach `8.8.8.8`.
* **Fix:** Verify your machine is connected to Wi-Fi/cellular. (Using `8.8.8.8` intentionally bypasses standard domain blocking, which is especially useful when testing on strict campus networks or corporate firewalls).

## Author
Tommy Csete - Localization Group
