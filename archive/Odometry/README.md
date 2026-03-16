# Odometry Node (IMU + SLAM)

This package provides a simple ROS2 node that publishes a unified
nav_msgs/msg/Odometry message by combining data from SLAM and the IMU.

The goal is to provide a single /odom topic that other nodes
(navigation, localization, controllers, etc.) can subscribe to.

This node performs very little processing. It mainly merges the
relevant fields from SLAM and IMU into one odometry message.

---

# Overview

Inputs

SLAM odometry topic

/odometry

Message type

nav_msgs/msg/Odometry

Used fields from SLAM

- pose.pose.position (x, y, z)
- pose.pose.orientation
- twist.twist.linear if available
- pose covariance if available
- twist covariance if available

IMU topic

/imu/data

Message type

sensor_msgs/msg/Imu

Used field from IMU

- angular_velocity

Output topic

/odom

Message type

nav_msgs/msg/Odometry

---

# What This Node Does

1. Subscribes to SLAM odometry.
2. Subscribes to IMU data.
3. Creates a new nav_msgs/Odometry message.
4. Copies the following from SLAM:
   - position
   - orientation
   - covariance values
5. Uses SLAM linear velocity if available, or estimates it from pose changes.
6. Copies angular velocity from the IMU gyro.
7. Publishes the combined result on /odom.

This avoids integrating IMU acceleration, which would quickly
introduce drift. SLAM provides stable position while the IMU
provides accurate rotational velocity.

---

# Requirements From SLAM

SLAM must publish an odometry message on:

/odometry

The message type must be:

nav_msgs/msg/Odometry

Required fields

- header.stamp
- pose.pose.position.x
- pose.pose.position.y
- pose.pose.position.z
- pose.pose.orientation (quaternion)

Recommended fields

- twist.twist.linear.x
- pose covariance
- twist covariance

The current implementation preserves the frame_id and child_frame_id
coming from the SLAM odometry message.

If SLAM does not provide meaningful linear velocity, this node can
estimate it from pose differences between messages.

---
