from setuptools import find_packages, setup

package_name = 'local_path_generator'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=[
        'setuptools',
        'polyline',
    ],
    zip_safe=True,
    maintainer='ruangfafa',
    maintainer_email='ruangfafa@outlook.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'local_path_generator = local_path_generator.app.application:main',
        ],
    },
)
