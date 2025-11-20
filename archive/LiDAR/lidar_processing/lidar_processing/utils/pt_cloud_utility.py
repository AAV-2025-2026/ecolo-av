"""
Utility functions for point cloud processing.
These functions can be used by any node.
"""

import numpy as np

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
