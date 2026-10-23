"""
The car's cameras, with the 2024-25 calibrations. Linux only (usb_cam).

  ros2 launch aav_sensors cameras.launch.py [left:=/dev/aav/camera_left] [right:=]

  left   usb_cam -> /sensors/camera/front_left/image_raw, .../camera_info   camera_left_link
  right  usb_cam -> /sensors/camera/front_right/image_raw, .../camera_info  camera_right_link
         (only when right:= names a device)

The left camera is "the camera": the YOLO detector reads /sensors/camera/front_left/image_raw. The
calibrations are config/cameras/left.ini and right.ini, in ROS's own INI format, for
1920 x 1080. Untested on the car: the camera models are Q22, and their udev names need
filling in (tools/udev/99-aav.rules). On a Mac, bench mode's mock_camera stands in.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def camera(side, device, topic):
    calibration = PathJoinSubstitution([FindPackageShare('aav_sensors'), 'config', 'cameras',
                                        f'{side}.ini'])
    return Node(
        package='usb_cam', executable='usb_cam_node_exe', name=f'camera_{side}',
        parameters=[{
            'video_device': device,
            'image_width': 1920,
            'image_height': 1080,
            'framerate': 15.0,
            'pixel_format': 'mjpeg2rgb',       # most USB cameras only reach 1080p in MJPEG
            'frame_id': f'camera_{side}_link',
            'camera_name': f'narrow_stereo/{side}',   # the name inside the .ini file
            'camera_info_url': ['file://', calibration],
        }],
        remappings=[('image_raw', f'{topic}/image_raw'), ('camera_info', f'{topic}/camera_info')],
        condition=IfCondition(PythonExpression(["'", device, "' != ''"])),
    )


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('left', default_value='/dev/aav/camera_left'),
        DeclareLaunchArgument('right', default_value='',
                              description='the right camera, e.g. /dev/aav/camera_right'),
        camera('left', LaunchConfiguration('left'), '/sensors/camera/front_left'),
        camera('right', LaunchConfiguration('right'), '/sensors/camera/front_right'),
    ])
