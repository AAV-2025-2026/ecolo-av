#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from radar_msgs.msg import RadarScan
from geometry_msgs.msg import PointStamped
import numpy as np
import math

class RadarEKFTracker(Node):
    def __init__(self):
        super().__init__("radar_ekf_tracker_node")
        
        self.sub = self.create_subscription(RadarScan, "radar/scan", self.callback, 10)
        self.pub = self.create_publisher(PointStamped, "radar/tracked_point", 10)
        
        # EKF state: [x, y, vx, vy]
        self.x = np.zeros((4, 1))
        self.P = np.eye(4) * 10.0
        self.dt = 0.05  # 50ms update rate
        
        # Process noise
        self.Q = np.eye(4) * 0.1
        
        # Measurement noise
        self.R = np.eye(2) * 0.5
        
        self.get_logger().info("EKF Tracker Started")
        self.get_logger().info("Tracking first detection from /radar/scan")
    
    def callback(self, msg: RadarScan):
        if len(msg.returns) == 0:
            return
        
        # Track the first detection (you can extend this to track multiple objects)
        det = msg.returns[0]
        
        r = det.range
        th = det.azimuth
        rdot = det.doppler_velocity
        
        # Convert polar to Cartesian measurement
        z = np.array([
            [r * math.cos(th)],
            [r * math.sin(th)],
        ])
        
        # --------------------------
        # EKF PREDICT
        # --------------------------
        F = np.array([
            [1, 0, self.dt, 0],
            [0, 1, 0, self.dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])
        
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q
        
        # --------------------------
        # EKF UPDATE
        # --------------------------
        H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        y = z - (H @ self.x)
        S = H @ self.P @ H.T + self.R
        K = self.P @ H.T @ np.linalg.inv(S)
        
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ H) @ self.P
        
        # Publish tracked point
        p = PointStamped()
        p.header = msg.header
        p.point.x = float(self.x[0])
        p.point.y = float(self.x[1])
        p.point.z = 0.0
        
        self.pub.publish(p)
        
        self.get_logger().info(
            f"Tracking: pos=({self.x[0][0]:.2f}, {self.x[1][0]:.2f}) "
            f"vel=({self.x[2][0]:.2f}, {self.x[3][0]:.2f}) m/s, "
            f"raw: R={r:.2f}m, θ={math.degrees(th):.1f}°, v={rdot:.2f}m/s"
        )

def main(args=None):
    rclpy.init(args=args)
    node = RadarEKFTracker()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
