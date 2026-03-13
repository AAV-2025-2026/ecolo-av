from setuptools import find_packages, setup

package_name = 'aav_speed_control'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/launch', ['launch/vehicle_pid_stack.launch.py']),
        ('share/' + package_name + '/config', ['config/control_params.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AAV User',
    maintainer_email='user@example.com',
    description='Wheel encoder UDP receiver, speed estimator, and first-pass speed PID for the AAV.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'wheel_encoder_udp = aav_speed_control.wheel_encoder_udp_node:main',
            'speed_estimator = aav_speed_control.speed_estimator_node:main',
            'speed_pid = aav_speed_control.speed_pid_node:main',
        ],
    },
)
