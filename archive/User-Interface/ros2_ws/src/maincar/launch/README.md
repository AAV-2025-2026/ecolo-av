Below is the information you need to add to a systemd service.
This will allow launch_bootup.sh to execute on system boot:


[Unit]
Description=Launch ROS2 maincar nodes on boot
After=network.target

[Service]
Type=simple
User=alex
Environment="ROS_DOMAIN_ID=0"
Environment="ROS_NAMESPACE=maincar"
# make sure you source ROS2 and your workspace
ExecStart=/bin/bash -lc "/home/alex/repos/User-Interface/ros2_ws/src/maincar/launch/launch_bootup.sh"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
