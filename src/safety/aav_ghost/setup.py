from glob import glob

from setuptools import find_packages, setup

package_name = 'aav_ghost'

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
    description="Ghost obstacles: a pretend person in Nav2's view.",
    license='TODO',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'ghost_obstacle = aav_ghost.ghost_obstacle:main',
            'ghost = aav_ghost.ghost_cli:main',
        ],
    },
)
