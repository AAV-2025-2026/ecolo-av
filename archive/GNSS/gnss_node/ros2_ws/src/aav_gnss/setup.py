import os
from glob import glob
from setuptools import setup

package_name = 'aav_gnss'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
    ],
    install_requires=['setuptools', 'pyserial', 'pynmea2'],
    zip_safe=True,
    maintainer='Tommy Csete',
    description='AAV GNSS Publisher',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'gnss_node = aav_gnss.gnss_node:main'
        ],
    },
)