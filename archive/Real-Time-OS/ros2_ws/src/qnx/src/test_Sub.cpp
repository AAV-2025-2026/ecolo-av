#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"

#include <cstring>
#include <string>

// UDP sockets (Linux)
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

#pragma pack(push, 1)
struct ImuUdpPacket
{
  uint32_t seq;
  float ax, ay, az;  // linear accel
  float gx, gy, gz;  // gyro
};
#pragma pack(pop)

class QNX_sub_bridge : public rclcpp::Node
{
public:
  QNX_sub_bridge()
  : rclcpp::Node("qnx_sub_bridge"), seq_(0)
  {
    // --- params so you can change IP/port without changing code ---
    this->declare_parameter<std::string>("imu_topic", "/imu/data");
    this->declare_parameter<std::string>("qnx_ip", "192.168.1.50"); // teammate QNX VPN IP
    this->declare_parameter<int>("qnx_port", 9000);

    const auto topic = this->get_parameter("imu_topic").as_string();
    const auto ip    = this->get_parameter("qnx_ip").as_string();
    const int  port  = this->get_parameter("qnx_port").as_int();

    // --- UDP setup ---
    sock_ = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (sock_ < 0) {
      throw std::runtime_error("socket() failed");
    }

    std::memset(&dest_, 0, sizeof(dest_));
    dest_.sin_family = AF_INET;
    dest_.sin_port = htons(static_cast<uint16_t>(port));
    if (inet_pton(AF_INET, ip.c_str(), &dest_.sin_addr) != 1) {
      throw std::runtime_error("Bad qnx_ip (inet_pton failed)");
    }

    // --- ROS subscription ---
    sub_ = this->create_subscription<sensor_msgs::msg::Imu>(
      topic,
      rclcpp::SensorDataQoS(),
      std::bind(&QNX_sub_bridge::sub_callback, this, std::placeholders::_1)
    );

    RCLCPP_INFO(get_logger(), "Listening on %s, sending UDP to %s:%d",
                topic.c_str(), ip.c_str(), port);
  }

  ~QNX_sub_bridge() override
  {
    if (sock_ >= 0) ::close(sock_);
  }

private:
  void sub_callback(const sensor_msgs::msg::Imu::SharedPtr sub_msg)
  {
    ImuUdpPacket pkt{};
    pkt.seq = seq_++;

    pkt.ax = static_cast<float>(sub_msg->linear_acceleration.x);
    pkt.ay = static_cast<float>(sub_msg->linear_acceleration.y);
    pkt.az = static_cast<float>(sub_msg->linear_acceleration.z);

    pkt.gx = static_cast<float>(sub_msg->angular_velocity.x);
    pkt.gy = static_cast<float>(sub_msg->angular_velocity.y);
    pkt.gz = static_cast<float>(sub_msg->angular_velocity.z);

    ::sendto(sock_, &pkt, sizeof(pkt), 0,
             reinterpret_cast<sockaddr*>(&dest_), sizeof(dest_));
  }

  uint32_t seq_;
  int sock_{-1};
  sockaddr_in dest_{};

  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr sub_;
};

int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<QNX_sub_bridge>());
  rclcpp::shutdown();
  return 0;
}
