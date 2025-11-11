#! /usr/bin/env python3

"""LiDAR Subscriber Node
This node subscribes to LiDAR point cloud data, processes it"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
import sensor_msgs_py.point_cloud2 as pc2
import numpy as np

class LidarSubscriber(Node):

    def __init__(self):
        super().__init__('lidar_subscriber')
        self.declare_parameter('ptcloud2', '/velodyne_points')
        self.declare_parameter('max_range', 50.0)
        self.declare_parameter('min_range', 0.5)
        self.declare_parameter('logger_level', 10)

        self.topic = self.get_parameter('ptcloud2').value
        self.max_range = self.get_parameter('max_range').value
        self.min_range = self.get_parameter('min_range').value
        self.logger_level = self.get_parameter('logger_level').value

        self.subscription = self.create_subscription(
            PointCloud2,
            self.topic,
            self.lidar_callback,
            10)
        
        self.frame_count = 0

        self.get_logger().info('=================================')
        self.get_logger().info('VLP-16 LiDAR Subscriber Started')
        self.get_logger().info(f'Listening to: {self.topic}')
        self.get_logger().info(f'Range filter: {self.min_range}m - {self.max_range}m')
        self.get_logger().info('=================================')

    def filter_ptcloud(self, points):
        """
        Filter point cloud by distance range.
        
        Args:
            points: Nx4 numpy array (x, y, z, intensity)
            
        Returns:
            Filtered numpy array
        """
        distances = np.sqrt(points[:, 0]**2 + points[:, 1]**2 + points[:, 2]**2)
        mask = (distances >= self.min_range) & (distances <= self.max_range)
        return points[mask]
    
    def lidar_callback(self, msg):
        """
        Process incoming LiDAR point cloud message.
        
        Args:
            msg: PointCloud2 message
        """
        self.frame_count += 1
        
        # Convert ROS PointCloud2 to numpy array
        points_list = []
        for point in pc2.read_points(msg, field_names=("x", "y", "z", "intensity"), skip_nans=True):
            points_list.append([point[0], point[1], point[2], point[3]])
        
        if len(points_list) == 0:
            self.get_logger().warn('Received empty point cloud!')
            return
        
        points_array = np.array(points_list)
        
        # Apply range filter
        filtered_points = self.filter_ptcloud(points_array)
        
        # Log statistics periodically
        if self.frame_count % self.logger_level == 0:
            self.log_statistics(msg, points_array, filtered_points)
        
        # Process the filtered point cloud
        self.process_ptcloud(filtered_points)

    def log_statistics(self, msg, original_points, filtered_points):
        """Log point cloud statistics."""
        self.get_logger().info(f'\n{"="*50}')
        self.get_logger().info(f'Frame: {self.frame_count}')
        self.get_logger().info(f'Timestamp: {msg.header.stamp.sec}.{msg.header.stamp.nanosec}')
        self.get_logger().info(f'Frame ID: {msg.header.frame_id}')
        self.get_logger().info(f'Original points: {len(original_points)}')
        self.get_logger().info(f'Filtered points: {len(filtered_points)}')
        
        if len(filtered_points) > 0:
            self.get_logger().info(f'X: [{filtered_points[:, 0].min():.2f}, {filtered_points[:, 0].max():.2f}] m')
            self.get_logger().info(f'Y: [{filtered_points[:, 1].min():.2f}, {filtered_points[:, 1].max():.2f}] m')
            self.get_logger().info(f'Z: [{filtered_points[:, 2].min():.2f}, {filtered_points[:, 2].max():.2f}] m')
            self.get_logger().info(f'Intensity: [{filtered_points[:, 3].min():.0f}, {filtered_points[:, 3].max():.0f}]')
        
        self.get_logger().info(f'{"="*50}')    

    def process_ptcloud(self, points):
        """
        Main processing function for point cloud.
        Add your custom processing here (object detection, etc.)
        
        Args:
            points: Nx4 numpy array of filtered points
        """
        # TODO: Add your processing logic here
        # For now, just pass
        pass


def main(args=None):
    """Main function to run the node."""
    rclpy.init(args=args)
    
    lidar_subscriber = LidarSubscriber()
    
    try:
        rclpy.spin(lidar_subscriber)
    except KeyboardInterrupt:
        lidar_subscriber.get_logger().info('Keyboard interrupt detected')
    finally:
        lidar_subscriber.get_logger().info('Shutting down LiDAR subscriber...')
        lidar_subscriber.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()