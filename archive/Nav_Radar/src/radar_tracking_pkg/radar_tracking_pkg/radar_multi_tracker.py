#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from radar_msgs.msg import RadarScan
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header
import numpy as np
import struct
import math

class RadarMultiTracker(Node):
    def __init__(self):
        super().__init__("radar_multi_tracker")
        
        self.sub = self.create_subscription(RadarScan, "radar/scan", self.callback, 10)
        self.pub = self.create_publisher(PointCloud2, "radar/all_tracks", 10)
        
        # Store recent detections (track_id -> data)
        self.tracks = {}
        self.track_timeout = 1.0  # seconds
        
        self.get_logger().info("Multi-Target Tracker Started")
        self.get_logger().info("Publishing all tracks to /radar/all_tracks")
    
    def callback(self, msg: RadarScan):
        current_time = self.get_clock().now().nanoseconds / 1e9
        
        if len(msg.returns) == 0:
            return
        
        det = msg.returns[0]
        r = det.range
        th = det.azimuth
        v = det.doppler_velocity
        
        # Convert to Cartesian
        x = r * math.cos(th)
        y = r * math.sin(th)
        
        # Use range/angle as a simple track ID (group similar detections)
        track_key = f"{int(r)}_{int(math.degrees(th))}"
        
        self.tracks[track_key] = {
            'x': x,
            'y': y,
            'z': 0.0,
            'velocity': v,
            'time': current_time
        }
        
        # Remove old tracks
        self.tracks = {
            k: v for k, v in self.tracks.items() 
            if (current_time - v['time']) < self.track_timeout
        }
        
        # Publish all active tracks as PointCloud2
        self.publish_pointcloud(msg.header)
        
        self.get_logger().info(
            f"Active tracks: {len(self.tracks)} | "
            f"Latest: R={r:.1f}m, θ={math.degrees(th):.1f}°, v={v:.1f}m/s at ({x:.1f}, {y:.1f})"
        )
    
    def publish_pointcloud(self, header):
        if len(self.tracks) == 0:
            return
        
        # Create PointCloud2 message
        points = []
        for track in self.tracks.values():
            # Pack as x, y, z, intensity (velocity)
            points.append([track['x'], track['y'], track['z'], track['velocity']])
        
        # Create PointCloud2
        cloud = PointCloud2()
        cloud.header = header
        cloud.header.frame_id = "radar_link"
        
        cloud.height = 1
        cloud.width = len(points)
        cloud.is_dense = False
        cloud.is_bigendian = False
        
        # Define fields: x, y, z, intensity
        cloud.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1),
        ]
        
        cloud.point_step = 16  # 4 fields * 4 bytes each
        cloud.row_step = cloud.point_step * cloud.width
        
        # Pack data
        buffer = []
        for point in points:
            buffer.append(struct.pack('ffff', point[0], point[1], point[2], point[3]))
        
        cloud.data = b''.join(buffer)
        
        self.pub.publish(cloud)

def main(args=None):
    rclpy.init(args=args)
    node = RadarMultiTracker()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
