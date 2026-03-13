from setuptools import find_packages, setup

package_name = 'aav_uart_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/launch', ['launch/bridge.launch.py']),
        ('share/' + package_name + '/config', ['config/bridge_params.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AAV User',
    maintainer_email='user@example.com',
    description='UART bridge from ROS 2 Ackermann commands to ESP32 framed actuator commands.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'ackermann_uart_bridge = aav_uart_bridge.ackermann_uart_bridge:main',
        ],
    },
)
