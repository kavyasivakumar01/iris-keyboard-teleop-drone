from setuptools import find_packages, setup

package_name = 'iris_keyboard_teleop'

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
    maintainer='Kavya Sivakumar',
    maintainer_email='kavyasiva1008@gmail.com',
    description='Keyboard teleoperation of an ArduPilot Iris quadcopter in Gazebo via MAVROS',
    license='MIT',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'teleop = iris_keyboard_teleop.teleop_node:main',
        ],
    },
)