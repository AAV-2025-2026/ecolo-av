from setuptools import setup

package_name = 'yolo_ros2'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='aav',
    maintainer_email='your_email@example.com',
    description='YOLO ROS2 inference node',
    license='Apache License 2.0',
    tests_require=['pytest'],
    data_files=[
    ('share/ament_index/resource_index/packages',
        ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
    ],
    entry_points={
        'console_scripts': [
            'yolo_inference = yolo_ros2.yolo_inference:main',
        ],
    },
)

