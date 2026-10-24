from setuptools import setup

package_name = 'odometry_node'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='your_name',
    maintainer_email='your_email@example.com',
    description='Simple ROS2 odometry node that combines SLAM odometry and IMU data into a unified /odom topic.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'odometry_node = odometry_node.odometry_node:main',
        ],
    },
)