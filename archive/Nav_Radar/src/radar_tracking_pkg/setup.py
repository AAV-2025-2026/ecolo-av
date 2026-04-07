from setuptools import setup
from glob import glob

package_name = 'radar_tracking_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Vaasu Jindal',
    maintainer_email='vaasujindal@cmail.carleton.ca',
    description='Delphi ESR 2.5 Radar Processing Pipeline (ROS2)',
    license='MIT',
    entry_points={
        'console_scripts': [
            'radar_serial_publisher = radar_tracking_pkg.radar_serial_publisher:main',
            'radar_decoder = radar_tracking_pkg.radar_decoder:main',
            'radar_pointcloud = radar_tracking_pkg.radar_pointcloud:main',
            'radar_markers = radar_tracking_pkg.radar_markers:main',
            'radar_ekf_tracker = radar_tracking_pkg.radar_ekf_tracker:main',
            'radar_diagnostics = radar_tracking_pkg.radar_diagnostics:main',
        ],
    },
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
        ('share/' + package_name, ['package.xml']),
    ],
)

