#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from radar_msgs.msg import RadarScan, RadarReturn
import math


def int8(x):
    return x - 256 if x > 127 else x


class RadarDecoder(Node):
    def __init__(self):
        super().__init__("radar_decoder")

        self.sub = self.create_subscription(
            String,
            "radar/raw_can",
            self.cb,
            50
        )

        self.pub = self.create_publisher(
            RadarScan,
            "radar/scan",
            10
        )

        self.get_logger().info(
            "ESR 2.5 Decoder running (ATU scaling: 0.0625 m)"
        )

    def cb(self, msg):
        try:
            can_id_hex, data_hex = msg.data.split("#")
            can_id = int(can_id_hex, 16)
            data = [int(x, 16) for x in data_hex.split()]
        except Exception:
            return

        # Track messages only
        if not (0x4E0 <= can_id <= 0x4E7):
            return

        if len(data) < 8:
            return

        # ---- ATU / Delphi ESR decoding ----

        # Range: 0.0625 m per LSB
        raw_range = data[0] | (data[1] << 8)
        range_m = raw_range * 0.0625

        # Azimuth: signed int8, 0.1 deg per LSB
        azimuth_deg = int8(data[2]) * 0.1

        # Velocity: signed int8, 0.1 m/s per LSB
        velocity = int8(data[3]) * 0.1

        status = data[4]

        # Invalid / empty track
        if status & 0x80:
            return

        det = RadarReturn()
        det.range = range_m
        det.azimuth = math.radians(azimuth_deg)
        det.doppler_velocity = velocity

        scan = RadarScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = "radar_link"
        scan.returns = [det]

        self.pub.publish(scan)


def main(args=None):
    rclpy.init(args=args)
    node = RadarDecoder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Header
from radar_msgs.msg import RadarScan, RadarReturn
import math


def int8(x):
    return x - 256 if x > 127 else x

class RadarDecoder(Node):
    def __init__(self):
        super().__init__("radar_decoder")

        self.sub = self.create_subscription(
            String, "radar/raw_can", self.cb, 50)

        self.pub = self.create_publisher(
            RadarScan, "radar/scan", 10)

        self.get_logger().info("ESR 2.5 Decoder running (0.01m scaling)")

    def cb(self, msg):
        try:
            can_id_hex, data_hex = msg.data.split("#")
            can_id = int(can_id_hex, 16)
            data = [int(x, 16) for x in data_hex.split()]
        except Exception:
            return

        if not (0x4E0 <= can_id <= 0x4E7):
            return
        if len(data) < 8:
            return

        # Decode
        raw_range = data[0] | (data[1] << 8)
        range_m = raw_range * 0.01

        azimuth = int8(data[2]) * 0.1
        velocity = int8(data[3]) * 0.1
        status = data[4]

        # Filter invalid
        if status & 0x80:
            return

        det = RadarReturn()
        det.range = range_m
        det.azimuth = math.radians(azimuth)
        det.doppler_velocity = velocity

        scan = RadarScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = "radar_link"
        scan.returns = [det]

        self.pub.publish(scan)
        
def main(args=None):
    rclpy.init(args=args)
    node = RadarDecoder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()


