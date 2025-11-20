"""
Utility functions for point cloud processing.
These functions can be used by any node.
"""

import numpy as np
from sensor_msgs.msg import PointCloud2, PointField
import sensor_msgs_py.point_cloud2 as pc2

def filter_ptcloud(points, min_range=0.5, max_range=50.0):
    """
    Filter point cloud by distance range.
    Args:
        points: Nx4 numpy array (x, y, z, intensity)
        min_range: min allowed distance (meters)
        max_range: max allowed distance (meters)
    Returns:
        Filtered numpy array
    """
    distances = np.sqrt(points[:, 0]**2 + points[:, 1]**2 + points[:, 2]**2)
    mask = (distances >= min_range) & (distances <= max_range)
    return points[mask]

def numpy_to_pointcloud2(points, header):
    """
    Converts an Nx3 or Nx4 numpy array (xyz[,intensity]) to a PointCloud2 message.

    Args:
        points: Nx3 (or Nx4) numpy array
        header: ROS message header (std_msgs/Header)

    Returns:
        sensor_msgs.msg.PointCloud2
    """
    # Check if intensity is included, if not, add dummy intensity=0
    if points.shape[1] == 3:
        points = np.hstack([points, np.zeros((points.shape[0], 1), dtype=points.dtype)])
    fields = [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1)
    ]
    return pc2.create_cloud(header, fields, points)