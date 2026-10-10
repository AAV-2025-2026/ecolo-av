from setuptools import find_packages, setup

package_name = 'battery_monitor'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('lib/' + package_name, [package_name+'/VEDirect.py']),
        ('lib/' + package_name, [package_name+'/BatteryStatePublisher.py']),
        ('lib/' + package_name, [package_name+'/HeartbeatPublisher.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='batmon',
    maintainer_email='batmon@todo.todo',
    description='TODO: Package description',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'battery_monitor = battery_monitor.battery_monitor:main'
        ],
    },
)
