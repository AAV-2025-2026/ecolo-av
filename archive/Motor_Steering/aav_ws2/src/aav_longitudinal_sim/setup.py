from setuptools import setup

package_name = 'aav_longitudinal_sim'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='seed',
    maintainer_email='seed@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
         'plant_node = aav_longitudinal_sim.plant_node:main',
        'speed_controller = aav_longitudinal_sim.speed_controller:main',
        'speed_profile_node = aav_longitudinal_sim.speed_profile_node:main',
        'imu_speed_controller = aav_longitudinal_sim.imu_speed_controller:main',
        ],
    },
)
