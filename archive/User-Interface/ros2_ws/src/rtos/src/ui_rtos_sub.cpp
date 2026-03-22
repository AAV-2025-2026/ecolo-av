#include <memory>
#include <functional>
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"

#include <iostream>
#include <cstring>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

struct IMUPacket{ //container representing the structure in which the messages will be stored and sent over at every callback
  float ang_vel_x;
  float ang_vel_y;
  float ang_vel_z;
  float lin_acc_x;
  float lin_acc_y;
  float lin_acc_z;
};


class QNXSub : public rclcpp::Node
{
 //UDP setup
  int sock = socket(AF_INET, SOCK_DGRAM, 0);
      // AF_INET = IPv4, SOCK_DGRAM = UDP behavior, 0 = default protocol for this socket type

  struct sockaddr_in dest; //sockaddr_in is structure type of IPv4 socket address
                              //dest = instance of that structure

  public:
    QNXSub(): Node("qnx_sub"), count_(0)
    {
      subscription_ = this->create_subscription<sensor_msgs::msg::Imu>(
      "qnx_imu", 10, std::bind(&QNXSub::topic_callback, this, std::placeholders::_1));
      
      memset(&dest, 0, sizeof(dest)); //clear the entire structure to zero within the instance of the IPv4 structure
      dest.sin_family = AF_INET; //defines the address as an IPv4 address
      dest.sin_port = htons(5000); //set the destination port (send on and listen on)
      dest.sin_addr.s_addr = inet_addr("127.0.0.1"); //set the destination IP address, right now set to local host, later change to IP address of the computer that will have the receiving UPD socket
    }

    ~QNXSub(){
      close(sock);
    }

  private:
    void topic_callback(const sensor_msgs::msg::Imu::SharedPtr msg) 
    {
      IMUPacket packet;

      packet.ang_vel_x = msg->angular_velocity.x;
      packet.ang_vel_y = msg->angular_velocity.y;
      packet.ang_vel_z = msg->angular_velocity.z;
      packet.lin_acc_x = msg->linear_acceleration.x;
      packet.lin_acc_y = msg->linear_acceleration.y;
      packet.lin_acc_z = msg->linear_acceleration.z;


      double Ang_Vel_x = msg->angular_velocity.x;
      double Ang_Vel_y = msg->angular_velocity.y;
      double Ang_Vel_z = msg->angular_velocity.z;
      double Lin_Acc_x = msg->linear_acceleration.x;
      double Lin_Acc_y = msg->linear_acceleration.y;
      double Lin_Acc_z = msg->linear_acceleration.z;
      RCLCPP_INFO(this->get_logger(), "Publishing IMU: %zu  |  angular_velocity = [%.2f,%.2f,%.2f] linear_acceleration = [%.2f,%.2f,%.2f]", 
        count_, Ang_Vel_x, Ang_Vel_y, Ang_Vel_z, Lin_Acc_x, 
        Lin_Acc_y, Lin_Acc_z);

      sendto(sock, &packet, sizeof(packet), 0, (sockaddr*)&dest, sizeof(dest));
      count_++;
      return;
    }
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr subscription_;
    size_t count_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<QNXSub>());
  rclcpp::shutdown();
  return 0;
}