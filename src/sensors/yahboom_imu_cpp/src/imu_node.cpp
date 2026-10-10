#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "sensor_msgs/msg/magnetic_field.hpp"
#include "yahboom_imu_cpp/serial_port.hpp"
#include <cstring>
#include <thread>
#include <atomic>
#include <cmath>

#define HEADER    0x55
#define TYPE_ACC  0x51
#define TYPE_GYRO 0x52
#define TYPE_ANGL 0x53
#define TYPE_MAG  0x54

static int16_t toInt16(uint8_t lo, uint8_t hi)
{
  return (int16_t)((hi << 8) | lo);
}

class ImuNode : public rclcpp::Node
{
public:
  // Constructor
  ImuNode()
  : Node("yahboom_imu_node")
  {
    declare_parameter("port", "/dev/aav/imu");  // udev name: tools/udev/99-aav.rules
    declare_parameter("baud_rate", 115200);
    declare_parameter("frame_id", "imu_link");
    // 1-sigma noise, published as covariance: robot_localization treats an
    // all-zero covariance as a perfect sensor. Starting guesses; measure them.
    declare_parameter("gyro_stddev", 0.02);        // rad/s
    declare_parameter("accel_stddev", 0.2);        // m/s^2

    // Get parameters
    auto port = get_parameter("port").as_string();
    auto baud = get_parameter("baud_rate").as_int();
    frame_id_ = get_parameter("frame_id").as_string();
    gyro_var_ = std::pow(get_parameter("gyro_stddev").as_double(), 2);
    accel_var_ = std::pow(get_parameter("accel_stddev").as_double(), 2);

    // Publishers
    imu_pub_ = create_publisher<sensor_msgs::msg::Imu>("/imu/data_raw", 10);
    mag_pub_ = create_publisher<sensor_msgs::msg::MagneticField>("/imu/mag", 10);

    // Open serial port
    serial_ = std::make_unique<SerialPort>(port, (int)baud);
    RCLCPP_INFO(get_logger(), "Opened %s at %ld baud", port.c_str(), baud);

    // Start reading thread
    running_ = true;
    read_thread_ = std::thread(&ImuNode::readLoop, this);
  }

  ~ImuNode()
  {
    running_ = false;
    if (read_thread_.joinable()) {
      read_thread_.join();
    }
  }

private:
  void readLoop()
  {
    uint8_t packet[11];

    while (running_ && rclcpp::ok()) {
      // Sync to header
      uint8_t byte;
      if (serial_->readByte(byte) <= 0) {continue;}
      if (byte != 0x55) {continue;}

      // Read remaining 10 bytes as one chunk
      uint8_t rest[10];
      int got = serial_->readBytes(rest, 10);
      if (got < 10) {continue;}

      // Assemble packet
      packet[0] = 0x55;
      memcpy(packet + 1, rest, 10);

      // Validate checksum
      uint8_t sum = 0;
      for (int i = 0; i < 10; i++) {sum += packet[i];}
      if (sum != packet[10]) {
        RCLCPP_WARN(get_logger(), "Checksum mismatch");
        continue;
      }

      parsePacket(packet);
    }
  }

  void parsePacket(uint8_t * p)
  {
    // p[0] is header, p[1] is type, p[2..9] are data, p[10] is checksum
    uint8_t type = p[1];
    int16_t r[4];
    for (int i = 0; i < 4; i++) {
      r[i] = toInt16(p[2 + i * 2], p[3 + i * 2]);
    }

    auto now = get_clock()->now();

    // Convert raw readings to physical units
    if (type == TYPE_ACC) {     // 16g range, 32768 = 16*9.8 m/s²
      acc_[0] = r[0] / 32768.0 * 16.0 * 9.8;
      acc_[1] = r[1] / 32768.0 * 16.0 * 9.8;
      acc_[2] = r[2] / 32768.0 * 16.0 * 9.8;
    } else if (type == TYPE_GYRO) {   // 2000°/s range, 32768 = 2000°/s
      gyro_[0] = r[0] / 32768.0 * 2000.0 * M_PI / 180.0;
      gyro_[1] = r[1] / 32768.0 * 2000.0 * M_PI / 180.0;
      gyro_[2] = r[2] / 32768.0 * 2000.0 * M_PI / 180.0;
    } else if (type == TYPE_MAG) {   // 1000µT range, 32768 = 1000µT
      mag_[0] = (float)r[0];
      mag_[1] = -(float)r[1];
      mag_[2] = (float)r[2];
    } else if (type == TYPE_ANGL) {   // ignore for now
      auto imu_msg = sensor_msgs::msg::Imu();
      imu_msg.header.stamp = now;
      imu_msg.header.frame_id = frame_id_;
      imu_msg.linear_acceleration.x = acc_[0];
      imu_msg.linear_acceleration.y = acc_[1];
      imu_msg.linear_acceleration.z = acc_[2];
      imu_msg.angular_velocity.x = gyro_[0];
      imu_msg.angular_velocity.y = gyro_[1];
      imu_msg.angular_velocity.z = gyro_[2];
      imu_msg.orientation_covariance[0] = -1.0;
      for (int i : {0, 4, 8}) {
        imu_msg.angular_velocity_covariance[i] = gyro_var_;
        imu_msg.linear_acceleration_covariance[i] = accel_var_;
      }
      imu_pub_->publish(imu_msg);

      auto mag_msg = sensor_msgs::msg::MagneticField();
      mag_msg.header.stamp = now;
      mag_msg.header.frame_id = frame_id_;
      mag_msg.magnetic_field.x = mag_[0];
      mag_msg.magnetic_field.y = mag_[1];
      mag_msg.magnetic_field.z = mag_[2];
      mag_pub_->publish(mag_msg);
    }
  }

  // Publishers
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_pub_;
  rclcpp::Publisher<sensor_msgs::msg::MagneticField>::SharedPtr mag_pub_;

  // Serial
  std::unique_ptr<SerialPort> serial_;

  // Thread - must be declared BEFORE running_ for correct destruction order
  std::atomic<bool> running_{false};
  std::thread read_thread_;

  // State
  std::string frame_id_;
  double gyro_var_ = 0.0;
  double accel_var_ = 0.0;
  double acc_[3] = {0};
  double gyro_[3] = {0};
  float mag_[3] = {0};
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<ImuNode>());
  rclcpp::shutdown();
  return 0;
}
