from setuptools import setup

package_name = 'aav_motor_sim'

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
    description='Motor simulation and automatic test nodes for AAV project',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'motor_sim_node   = aav_motor_sim.motor_sim_node:main',
            'motor_sim_tester = aav_motor_sim.motor_sim_tester:main',
        ],
    },
)

