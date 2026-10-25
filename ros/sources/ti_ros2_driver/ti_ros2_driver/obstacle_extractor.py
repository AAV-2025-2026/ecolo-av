from collections import deque

from geometry_msgs.msg import Pose, PoseArray
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import PointCloud2, PointField
import std_msgs.msg


class ObstacleExtractor(Node):
    def __init__(self):
        super().__init__('radar_obstacle_extractor')

        self.declare_parameter('input_topic', '/ti_radar_0/ti_mmwave_0')
        self.declare_parameter('output_topic', '/ti_radar_0/ti_mmwave_0_objects')
        self.declare_parameter('nav_output_topic', '/navigation_objects')
        self.declare_parameter('frame_id', '')
        self.declare_parameter('cluster_tolerance', 0.75)
        self.declare_parameter('z_tolerance', 0.75)
        self.declare_parameter('min_cluster_size', 1)
        self.declare_parameter('max_distance', 20.0)
        self.declare_parameter('min_distance', 0.05)
        self.declare_parameter('min_height', -2.0)
        self.declare_parameter('max_height', 3.0)

        self.input_topic = self.get_parameter('input_topic').value
        self.output_topic = self.get_parameter('output_topic').value
        self.nav_output_topic = self.get_parameter('nav_output_topic').value
        self.frame_override = self.get_parameter('frame_id').value
        self.cluster_tolerance = float(self.get_parameter('cluster_tolerance').value)
        self.z_tolerance = float(self.get_parameter('z_tolerance').value)
        self.min_cluster_size = int(self.get_parameter('min_cluster_size').value)
        self.max_distance = float(self.get_parameter('max_distance').value)
        self.min_distance = float(self.get_parameter('min_distance').value)
        self.min_height = float(self.get_parameter('min_height').value)
        self.max_height = float(self.get_parameter('max_height').value)

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.subscription = self.create_subscription(
            PointCloud2, self.input_topic, self.callback, qos
        )
        self.publisher = self.create_publisher(PointCloud2, self.output_topic, qos)
        self.nav_publisher = self.create_publisher(PoseArray, self.nav_output_topic, 10)
        self.log_counter = 0
        self.get_logger().info(
            f'Subscribing to {self.input_topic}, '
            f'publishing obstacle centroids to {self.output_topic}, '
            f'and navigation poses to {self.nav_output_topic}'
        )

    def callback(self, msg: PointCloud2) -> None:
        points = self.pointcloud2_to_numpy(msg)
        if points.size == 0:
            empty_objects = np.empty((0, 8), dtype=np.float32)
            self.publisher.publish(self.build_output(msg.header, empty_objects))
            self.nav_publisher.publish(self.build_pose_array(msg.header, empty_objects))
            return

        xyz = points[:, :3]
        ranges = np.linalg.norm(xyz, axis=1)
        valid = np.isfinite(points).all(axis=1)
        valid &= (ranges >= self.min_distance) & (ranges <= self.max_distance)
        valid &= (points[:, 2] >= self.min_height) & (points[:, 2] <= self.max_height)
        points = points[valid]

        if points.size == 0:
            empty_objects = np.empty((0, 8), dtype=np.float32)
            self.publisher.publish(self.build_output(msg.header, empty_objects))
            self.nav_publisher.publish(self.build_pose_array(msg.header, empty_objects))
            return

        clusters = self.cluster_points(points[:, :3])
        objects = []
        for cluster in clusters:
            if len(cluster) < self.min_cluster_size:
                continue
            cluster_points = points[cluster]
            centroid = cluster_points[:, :3].mean(axis=0)
            distance = np.linalg.norm(centroid)
            avg_velocity = (
                float(cluster_points[:, 4].mean()) if cluster_points.shape[1] > 4 else 0.0
            )
            extent = (
                np.ptp(cluster_points[:, :3], axis=0)
                if len(cluster) > 1
                else np.zeros(3, dtype=np.float32)
            )
            objects.append(
                [
                    centroid[0],
                    centroid[1],
                    centroid[2],
                    distance,
                    avg_velocity,
                    extent[0],
                    extent[1],
                    extent[2],
                ]
            )

        object_array = (
            np.asarray(objects, dtype=np.float32)
            if objects
            else np.empty((0, 8), dtype=np.float32)
        )
        self.publisher.publish(self.build_output(msg.header, object_array))
        self.nav_publisher.publish(self.build_pose_array(msg.header, object_array))
        self.log_objects(object_array)

    def cluster_points(self, xyz: np.ndarray):
        n = xyz.shape[0]
        visited = np.zeros(n, dtype=bool)
        sq_tol = self.cluster_tolerance * self.cluster_tolerance
        clusters = []

        for start in range(n):
            if visited[start]:
                continue
            visited[start] = True
            queue = deque([start])
            cluster = [start]

            while queue:
                idx = queue.popleft()
                deltas = xyz - xyz[idx]
                dist2_xy = deltas[:, 0] ** 2 + deltas[:, 1] ** 2
                neighbor_mask = (dist2_xy <= sq_tol) & (np.abs(deltas[:, 2]) <= self.z_tolerance)
                neighbors = np.where(neighbor_mask)[0]
                for neighbor in neighbors:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        queue.append(neighbor)
                        cluster.append(neighbor)
            clusters.append(cluster)
        return clusters

    def pointcloud2_to_numpy(self, msg: PointCloud2) -> np.ndarray:
        if msg.width == 0 or msg.point_step == 0:
            return np.empty((0, 5), dtype=np.float32)

        field_names = [field.name for field in msg.fields]
        required = ['x', 'y', 'z']
        if not all(name in field_names for name in required):
            self.get_logger().warning('Incoming PointCloud2 does not contain x/y/z fields.')
            return np.empty((0, 5), dtype=np.float32)

        count = msg.width * msg.height
        raw = np.frombuffer(msg.data, dtype=np.uint8)
        points = np.empty((count, 5), dtype=np.float32)
        offsets = {field.name: field.offset for field in msg.fields}
        for i in range(count):
            base = i * msg.point_step
            for j, name in enumerate(['x', 'y', 'z', 'intensity', 'velocity']):
                if name in offsets and base + offsets[name] + 4 <= raw.size:
                    start = base + offsets[name]
                    points[i, j] = np.frombuffer(
                        raw[start:start + 4],
                        dtype=np.float32,
                        count=1,
                    )[0]
                else:
                    points[i, j] = 0.0
        return points

    def build_output(self, header, objects: np.ndarray) -> PointCloud2:
        msg = PointCloud2()
        msg.header = std_msgs.msg.Header()
        msg.header.stamp = header.stamp
        msg.header.frame_id = self.frame_override if self.frame_override else header.frame_id
        msg.height = 1
        msg.width = int(objects.shape[0])
        msg.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='distance', offset=12, datatype=PointField.FLOAT32, count=1),
            PointField(name='avg_velocity', offset=16, datatype=PointField.FLOAT32, count=1),
            PointField(name='extent_x', offset=20, datatype=PointField.FLOAT32, count=1),
            PointField(name='extent_y', offset=24, datatype=PointField.FLOAT32, count=1),
            PointField(name='extent_z', offset=28, datatype=PointField.FLOAT32, count=1),
        ]
        msg.is_bigendian = False
        msg.point_step = 32
        msg.row_step = msg.point_step * msg.width
        msg.is_dense = bool(msg.width > 0)
        msg.data = objects.astype(np.float32, copy=False).tobytes()
        return msg

    def build_pose_array(self, header, objects: np.ndarray) -> PoseArray:
        pose_array = PoseArray()
        pose_array.header = std_msgs.msg.Header()
        pose_array.header.stamp = header.stamp
        pose_array.header.frame_id = (
            self.frame_override if self.frame_override else header.frame_id
        )

        for obj in objects:
            pose = Pose()
            pose.position.x = float(obj[0])
            pose.position.y = float(obj[1])
            pose.position.z = float(obj[2])
            pose.orientation.w = 1.0
            pose_array.poses.append(pose)

        return pose_array

    def log_objects(self, objects: np.ndarray) -> None:
        self.log_counter += 1
        if self.log_counter % 10 != 0:
            return
        if objects.shape[0] == 0:
            self.get_logger().info('No navigation objects detected in current frame.')
            return

        summary_parts = []
        for index, obj in enumerate(objects, start=1):
            summary_parts.append(
                f'obj{index}: x={obj[0]:.2f}, y={obj[1]:.2f}, z={obj[2]:.2f}, dist={obj[3]:.2f}m'
            )
        self.get_logger().info('Navigation objects -> ' + ' | '.join(summary_parts))


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleExtractor()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
