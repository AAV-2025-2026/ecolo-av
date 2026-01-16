from setuptools import find_packages, setup

package_name = 'steering_controller'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ubuntu1',
    maintainer_email='ubuntu1@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            "test_node = steering_controller.first_node:main",
            "imu_pub = steering_controller.MockImuPublisher:main",
            'imu_sub = steering_controller.imu_subscriber:main',
            "nav_pub = steering_controller.mock_NAV_Publisher:main",
            'nav_sub = steering_controller.nav_subscriber:main',
            "steer = steering_controller.test_steering:main",
            "steer_sub = steering_controller.steer_subscriber:main",
        ],
    },
)
