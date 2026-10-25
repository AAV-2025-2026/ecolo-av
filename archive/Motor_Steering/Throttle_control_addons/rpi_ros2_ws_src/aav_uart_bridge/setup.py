from setuptools import setup

package_name = "aav_uart_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/bridge.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="you",
    maintainer_email="you@example.com",
    description="ROS 2 AckermannDrive -> UART bridge to ESP32 (no micro-ROS)",
    license="MIT",
    entry_points={
        "console_scripts": [
            "ackermann_uart_bridge = aav_uart_bridge.ackermann_uart_bridge:main",
        ],
    },
)
