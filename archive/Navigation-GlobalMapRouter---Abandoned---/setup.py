from setuptools import find_packages, setup

package_name = 'global_map_router'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
	('lib/python3.12/site-packages/global_map_router', ['global_map_router/.env']),
    ],
    install_requires=[
	'setuptools',
    	'python-dotenv',
    	'requests',
    	'colorlog',
    	'urllib3',
    	'idna',
    	'charset-normalizer',
    	'certifi',
    ],
    zip_safe=True,
    maintainer='ruangfafa',
    maintainer_email='ruangfafa@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
		'global_map_router = global_map_router.app.application:main',
        ],
    },
)
