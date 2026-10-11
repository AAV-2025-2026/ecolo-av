from glob import glob

from setuptools import find_packages, setup

package_name = 'aav_yolo'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AAV 2026-27 team',
    maintainer_email='aav-team@todo.invalid',
    description='A YOLO detector (camera images in, vision_msgs detections out), a '
                'stop-sign watcher that holds the autonomous drivers at a stop sign, and '
                "camera_obstacles, which puts the detections on the road for Nav2's costmap.",
    license='TODO',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'detector = aav_yolo.detector:main',
            'stop_sign_watcher = aav_yolo.stop_sign_watcher:main',
            'camera_obstacles = aav_yolo.camera_obstacles:main',
        ],
    },
)
