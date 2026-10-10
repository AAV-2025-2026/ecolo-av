from glob import glob

from setuptools import find_packages, setup

package_name = 'aav_bench'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AAV 2026-27 team',
    maintainer_email='aav-team@todo.invalid',
    description="Bench mode's pretend sensors: IMU, GPS, battery and camera.",
    license='TODO',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'mock_imu = aav_bench.sensors:imu',
            'mock_gps = aav_bench.sensors:gps',
            'mock_battery = aav_bench.sensors:battery',
            'mock_camera = aav_bench.sensors:camera',
        ],
    },
)
