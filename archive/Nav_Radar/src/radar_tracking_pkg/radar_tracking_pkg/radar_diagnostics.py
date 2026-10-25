#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from radar_msgs.msg import RadarScan
import math

class RadarDiagnostics(Node):
    def __init__(self):
        super().__init__("radar_diagnostics")
        self.sub = self.create_subscription(RadarScan, "radar/scan", self.callback, 10)
        self.prev_ranges = {}
        self.get_logger().info("Radar Diagnostics Started - Checking for anomalies...")
    
    def callback(self, msg: RadarScan):
        if len(msg.returns) == 0:
            return
        
        det = msg.returns[0]
        r = det.range
        v = det.doppler_velocity
        th = math.degrees(det.azimuth)
        
        # Check velocity vs range consistency
        track_key = f"{int(r/100)*100}"  # Group by 100m bins
        
        if track_key in self.prev_ranges:
            prev_r = self.prev_ranges[track_key]
            range_change = r - prev_r
            
            # Check if velocity direction matches range change
            if v < 0 and range_change > 0:
                self.get_logger().warn(
                    f"⚠️  INCONSISTENT: v={v:.1f}m/s (approaching) but range increased {range_change:.1f}m!"
                )
            elif v > 0 and range_change < 0:
                self.get_logger().warn(
                    f"⚠️  INCONSISTENT: v={v:.1f}m/s (receding) but range decreased {range_change:.1f}m!"
                )
        
        self.prev_ranges[track_key] = r
        
        # Check for suspicious values
        flags = []
        if r > 2000:
            flags.append("🚩 Very far (>2km indoors suspicious)")
        if abs(v) > 50:
            flags.append("🚩 High velocity (>180 km/h)")
        if r < 1 and r > 0:
            flags.append("⚠️  Very close (<1m)")
        if abs(th) > 45:
            flags.append("📐 Wide angle (>45°)")
        
        status = "✅ Normal" if not flags else " | ".join(flags)
        
        self.get_logger().info(
            f"R={r:7.1f}m, θ={th:5.1f}°, v={v:6.1f}m/s | {status}"
        )

def main(args=None):
    rclpy.init(args=args)
    node = RadarDiagnostics()
    rclpy.spin(node)

if __name__ == "__main__":
    main()
