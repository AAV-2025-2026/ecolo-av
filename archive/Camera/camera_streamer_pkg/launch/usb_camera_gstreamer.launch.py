from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
       Node(
            package='gscam',
            executable='gscam_node',
            name='usb_camera',
            parameters=[{
                'camera_name': 'usb_cam',
                'camera_info_url': '',
                'frame_id': 'camera_frame',
                
                # GStreamer pipeline for USB camera with H.264 encoding
                'gscam_config': 'v4l2src device=/dev/video0 ! '
                'image/jpeg,width=1280,height=720,framerate=30/1 ! '
                'jpegdec ! '
                'videoconvert ! '
                'video/x-raw,format=RGB ! '
                'identity name=gscam_identity',
                
                'sync_sink': True,
                'use_gst_timestamps': False,
                'image_encoding': 'rgb8',
                'reopen_on_eof': True
            }],
            remappings=[
                ('camera/image_raw', '/camera/image_raw'),
                ('camera/camera_info', '/camera/camera_info')
            ]
        )
    ])