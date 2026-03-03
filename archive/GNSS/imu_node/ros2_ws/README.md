ros2_ws/
├── src/
│   ├── maincar/
│   │   ├── maincar/
│   │   │   ├── __init__.py
│   │   │   ├── sensor_imu.py       <--- Runs the IMU node (old, don't use this)
│   │   │   └── sensor_imu_two.py   <--- Runs the IMU node (new, use this)
│   │   ├── setup.py
│   │   └── package.xml             <--- contains 'colcon build' configuration for maincar package
│   └── my_utils/
│       └── imu_reader.py   <-- helpful modules if needed (not used, just used as reference)
