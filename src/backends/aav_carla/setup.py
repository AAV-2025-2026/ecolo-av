from glob import glob

from setuptools import find_packages, setup

package_name = 'aav_carla'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AAV 2026-27 team',
    maintainer_email='aav-team@todo.invalid',
    description='CARLA as the car, behind the same topics as the real one.',
    license='TODO',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'carla_adapter = aav_carla.carla_adapter:main',
        ],
    },
)
