# AAV GNSS Node

A robust, thread-safe GNSS Publisher for the u-blox ZED-F9R GNSS receiver, designed for the AAV. This package handles serial NMEA communication, performs blocking hardware self-tests, and manages a background RTK/NTRIP correction stream using `rtklib`.

## Directory Structure

```text
aav_gnss/
├── package.xml               # ROS 2 package manifest (dependencies & metadata)
├── setup.py                  # Python setup script for colcon build
├── setup.cfg                 # Setup configuration for script installation
├── resource/                 # ROS 2 resource index directory
│   └── aav_gnss              # Package marker file
├── scripts/                  # Utility and installation scripts
│   ├── install_setup.sh      # Automated installer for system dependencies & udev rules (from standalone)
│   └── launch_gps.sh         # Helper script to quickly launch the node (from standalone)
├── deploy/                   # Files for OS-level background execution
│   ├── aav_gnss.service      # systemd service template
│   └── start_gnss.sh         # Bash wrapper script to source ROS 2
├── aav_gnss/                 # Core Python package code
│   ├── __init__.py
│   ├── gnss_node.py          # Main ROS 2 node for NMEA parsing and publishing
│   └── gnss_self_test.py     # Blocking hardware validation checks
└── launch/                   # ROS 2 launch files
    └── gnss.launch.py        # Main launch script with RTK stream manager
```

## Prerequisites & Hardware Setup

Before building the ROS 2 package, you must install the required system dependencies and configure the Linux `udev` rules so the GPS receiver is consistently recognized.

1. Navigate to the package directory:
   ```bash
   cd ~/ros2_ws/src/aav_gnss
   ```
2. Run the included setup script (requires `sudo`):
   ```bash
   sudo ./scripts/install_setup.sh
   ```
3. **Important:** If the module is currently plugged via USB, unplug it and plug it back in. This allows the new `udev` rule to trigger, creating the `/dev/zed_f9r` symlink required by the node.

## Building the Workspace

Build the package using standard `colcon` commands from the root of your workspace. Make sure to source your ROS 2 Humble installation first:

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select aav_gnss
source install/setup.bash
```

## Running the Node

If you are opening a new terminal, remember to source both ROS 2 and your workspace:
```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
```

You can launch the GNSS node and the background RTK stream manager using the provided launch file. 

The launch file requires two arguments to authenticate with the NTRIP caster:
* `email`: Your registered email for rtk2go.
* `mountpoint`: The specific RTK base station stream (e.g., `CanalTerris`).

```bash
ros2 launch aav_gnss gnss.launch.py email:="your_email@example.com" mountpoint:="CanalTerris"
```

Alternatively, you can use the provided helper script but you must change the launch path within:
```bash
./scripts/launch_gps.sh
```

The node will wait for a valid GPS lock (passing the self-test criteria) before it begins publishing `sensor_msgs/NavSatFix` messages to the `/aav/gps/fix` topic.

## Systemd Deployment (Run on Boot)

For AAV deployment, you can configure the GNSS node to start automatically in the background as soon as the Pi boots up.

The deployment files are located in the `deploy/` directory.

### 1. Configure the Wrapper Script
Edit the `deploy/start_gnss.sh` script to include your actual workspace path and your specific RTK email and mountpoint arguments.

Copy the script to your home directory and make it executable:
```bash
cp deploy/start_gnss.sh ~/start_gnss.sh
chmod +x ~/start_gnss.sh
```

### 2. Configure the Service File
Edit `deploy/aav_gnss.service` and replace the placeholder tags (like `<YOUR_USER>` or the paths) with your actual system username and workspace directory.

Copy the configured service file to the Ubuntu systemd directory:
```bash
sudo cp deploy/aav_gnss.service /etc/systemd/system/
```

### 3. Enable and Start the Service
Reload the systemd daemon to register the new file, enable it to start on boot, and start the service immediately:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aav_gnss.service
sudo systemctl start aav_gnss.service
```

### 4. Viewing Background Logs
To view the live ROS 2 output and connection warnings while the service is running in the background, use `journalctl`:
```bash
journalctl -u aav_gnss.service -f
```

## Disabling or Removing the Service

If you need to switch back to manual development mode or want to prevent the node from starting automatically on boot, follow these steps:

### Stop and Disable (Recommended for Dev)
This stops the background process immediately and prevents it from starting on the next boot, but keeps your configuration files in place for future use.
```bash
# Stop the running service
sudo systemctl stop aav_gnss.service

# Prevent it from starting on boot
sudo systemctl disable aav_gnss.service
```

### Complete Removal
If you want to completely wipe the service configuration from your system:
```bash
sudo systemctl stop aav_gnss.service
sudo systemctl disable aav_gnss.service
sudo rm /etc/systemd/system/aav_gnss.service
sudo rm ~/start_gnss.sh
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

### Restarting the Service
To turn the auto-start back on at any time:
```bash
sudo systemctl enable aav_gnss.service
sudo systemctl start aav_gnss.service
```