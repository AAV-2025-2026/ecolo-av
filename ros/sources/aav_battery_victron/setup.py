from setuptools import find_packages, setup

package_name = 'aav_battery_victron'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='batmon',
    maintainer_email='batmon@todo.todo',
    description='Victron battery monitor (VE.Direct over serial) as sensor_msgs/BatteryState',
    license='Apache-2.0',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': ['battery_monitor = aav_battery_victron.battery_monitor:main'],
    },
)
