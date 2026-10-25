from setuptools import find_packages, setup

package_name = 'aav_gps_heading'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='AAV 2026-27 team',
    maintainer_email='aav-team@todo.invalid',
    description="The car's heading from the GPS receiver's velocity, for the global EKF.",
    license='TODO',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'gps_heading = aav_gps_heading.gps_heading:main',
        ],
    },
)
