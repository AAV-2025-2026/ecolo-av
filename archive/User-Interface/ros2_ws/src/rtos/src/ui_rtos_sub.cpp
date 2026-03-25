#include <memory>
#include <functional>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "sensor_msgs/msg/nav_sat_fix.hpp"

#include <iostream>
#include <cstring>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#include "message_structure.hpp"


class QNXSub : public rclcpp::Node
{
 //UDP setup
  int sock = socket(AF_INET, SOCK_DGRAM, 0);
      // AF_INET = IPv4, SOCK_DGRAM = UDP behavior, 0 = default protocol for this socket type

  struct sockaddr_in dest; //sockaddr_in is structure type of IPv4 socket address
                              //dest = instance of that structure

  // Latest GPS data
  double latitude_ = 0.0;
  double longitude_ = 0.0;
  double altitude_ = 0.0;

  public:
    QNXSub(): Node("qnx_sub"), imu_count(0), gps_count(0)
    {
      subscription_ = this->create_subscription<sensor_msgs::msg::Imu>(
      "qnx_imu", 10, std::bind(&QNXSub::imu_callback, this, std::placeholders::_1));

      subscription_gps_ = this->create_subscription<sensor_msgs::msg::NavSatFix>(
      "qnx_gps", 10, std::bind(&QNXSub::gps_callback, this, std::placeholders::_1));

      memset(&dest, 0, sizeof(dest)); //clear the entire structure to zero within the instance of the IPv4 structure
      dest.sin_family = AF_INET; //defines the address as an IPv4 address
      dest.sin_port = htons(5000); //set the destination port (send on and listen on)
      dest.sin_addr.s_addr = inet_addr("127.0.0.1"); //set the destination IP address, right now set to local host, later change to IP address of the computer that will have the receiving UPD socket
    }

    ~QNXSub(){
      close(sock);
    }

  private:
    void imu_callback(const sensor_msgs::msg::Imu::SharedPtr msg)
    {
      IMUPacket packet;

      packet.ang_vel_x = msg->angular_velocity.x;
      packet.ang_vel_y = msg->angular_velocity.y;
      packet.ang_vel_z = msg->angular_velocity.z;
      packet.lin_acc_x = msg->linear_acceleration.x;
      packet.lin_acc_y = msg->linear_acceleration.y;
      packet.lin_acc_z = msg->linear_acceleration.z;

      RCLCPP_INFO(this->get_logger(), "Publishing IMU: %zu  |  angular_velocity = [%.2f,%.2f,%.2f] linear_acceleration = [%.2f,%.2f,%.2f]",
        imu_count, packet.ang_vel_x, packet.ang_vel_y, packet.ang_vel_z, packet.lin_acc_x, packet.lin_acc_y, packet.lin_acc_z);

      sendto(sock, &packet, sizeof(packet), 0, (sockaddr*)&dest, sizeof(dest));
      imu_count++;
      return;
    }

    void gps_callback(const sensor_msgs::msg::NavSatFix::SharedPtr msg)
    {
      GPSPacket packet;

      packet.latitude = msg->latitude;
      packet.longitude = msg->longitude;
      packet.altitude = msg->altitude;
      RCLCPP_INFO(this->get_logger(), "Publishing GPS: %zu | latitude=%.6f, longitude=%.6f, altitude=%.2f",
        gps_count, packet.latitude, packet.longitude, packet.altitude);

      sendto(sock, &packet, sizeof(packet), 0, (sockaddr*)&dest, sizeof(dest));
      gps_count++;
      return;
    }
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr subscription_;
    rclcpp::Subscription<sensor_msgs::msg::NavSatFix>::SharedPtr subscription_gps_;
    size_t imu_count, gps_count;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<QNXSub>());
  rclcpp::shutdown();
  return 0;
}
