#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from radar_msgs.msg import RadarScan
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import ColorRGBA
import math

class RadarMarkers(Node):
    def __init__(self):
        super().__init__("radar_markers")
        
        self.sub = self.create_subscription(
            RadarScan, 
            "radar/scan", 
            self.callback, 
            10
        )
        
        self.pub = self.create_publisher(MarkerArray, "radar/markers", 10)
        
        self.get_logger().info("Radar Markers Publisher Started")
    
    def callback(self, msg: RadarScan):
        marker_array = MarkerArray()
        
        for i, det in enumerate(msg.returns):
            # Create sphere marker for each detection
            marker = Marker()
            marker.header = msg.header
            marker.ns = "radar_detections"
            marker.id = i
            marker.type = Marker.SPHERE
            marker.action = Marker.ADD
            
            # Position
            r = det.range
            theta = det.azimuth
            marker.pose.position.x = r * math.cos(theta)
            marker.pose.position.y = r * math.sin(theta)
            marker.pose.position.z = 0.5
            
            # Size based on signal strength
            marker.scale.x = 0.5
            marker.scale.y = 0.5
            marker.scale.z = 0.5
            
            # Color based on velocity
            v = det.doppler_velocity
            if v > 0:  # Receding
                marker.color = ColorRGBA(r=1.0, g=0.0, b=0.0, a=0.8)
            elif v < 0:  # Approaching
                marker.color = ColorRGBA(r=0.0, g=0.0, b=1.0, a=0.8)
            else:  # Stationary
                marker.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=0.8)
            
            marker.lifetime = rclpy.duration.Duration(seconds=0.5).to_msg()
            
            marker_array.markers.append(marker)
        
        self.pub.publish(marker_array)

def main(args=None):
    rclpy.init(args=args)
    node = RadarMarkers()
    rclpy.spin(node)

if __name__ == "__main__":
    main()
