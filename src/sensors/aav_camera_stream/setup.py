from glob import glob

from setuptools import find_packages, setup

package_name = 'aav_camera_stream'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/pi', glob('pi/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AAV 2026-27 team',
    maintainer_email='aav-team@todo.invalid',
    description="A camera's H.264 stream from MediaMTX on the camera Pi, decoded, undistorted "
                'and run through the detector in one process, per camera; detections out. '
                "And the camera Pi's MediaMTX settings.",
    license='TODO',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'camera_stream = aav_camera_stream.camera_stream:main',
        ],
    },
)
