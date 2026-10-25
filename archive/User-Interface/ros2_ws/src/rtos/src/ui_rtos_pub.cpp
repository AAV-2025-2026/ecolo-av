#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float32.hpp"
#include "std_msgs/msg/u_int8.hpp"
#include "sensor_msgs/msg/nav_sat_fix.hpp"
#include "sensor_msgs/msg/nav_sat_status.hpp"
#include "message_structure.hpp"

using namespace std::chrono_literals;

class QNXPublisher : public rclcpp::Node
{
public:
    QNXPublisher() : Node("qnx_udp_rtos_pub")
    {
        speed_publisher_ = this->create_publisher<std_msgs::msg::Float32>("/rtos/speed", 10);
        gear_publisher_ = this->create_publisher<std_msgs::msg::UInt8>("/rtos/gear", 10);
        gps_publisher_ = this->create_publisher<sensor_msgs::msg::NavSatFix>("/rtos/gps", 10);

        udp_thread_ = std::thread(&QNXPublisher::udp_listener, this);

        RCLCPP_INFO(this->get_logger(), "QNX UDP RTOS publisher initialized.");
    }

    ~QNXPublisher()
    {
        if (udp_thread_.joinable()) {
            udp_thread_.join();
        }
    }

private:
    void udp_listener()
    {
        const int UDP_PORT = 49200;
        int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
        if (sockfd < 0) {
            RCLCPP_ERROR(this->get_logger(), "Failed to create UDP socket");
            return;
        }

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(UDP_PORT);
        addr.sin_addr.s_addr = INADDR_ANY;

        if (bind(sockfd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
            RCLCPP_ERROR(this->get_logger(), "Failed to bind UDP socket");
            close(sockfd);
            return;
        }

        RCLCPP_INFO(this->get_logger(), "Listening for UDP on port %d", UDP_PORT);

        char buffer[1024];
        while (rclcpp::ok()) {
            sockaddr_in sender_addr{};
            socklen_t addr_len = sizeof(sender_addr);
            ssize_t len = recvfrom(sockfd, buffer, sizeof(buffer), 0,
                                   (struct sockaddr*)&sender_addr, &addr_len);
            if (len > 0) {
                PublisherMessageType message_type = static_cast<PublisherMessageType>(buffer[0]);
                switch (message_type) {
                    case PublisherMessageType::Speed: {
                        SpeedStruct speed;
                        memcpy(&speed, &buffer[1], sizeof(speed));
                        std_msgs::msg::Float32 speed_msg;
                        speed_msg.data = static_cast<float>(speed.speed);
                        speed_publisher_->publish(speed_msg);
                        RCLCPP_INFO(this->get_logger(), "Published /rtos/speed = %.3f", speed_msg.data);
                        break;
                    }
                    case PublisherMessageType::Location: {
                        LocationStruct location;
                        memcpy(&location, &buffer[1], sizeof(location));
                        sensor_msgs::msg::NavSatFix gps_msg;
                        gps_msg.header.stamp = this->get_clock()->now();
                        gps_msg.header.frame_id = "rtos_gps";
                        gps_msg.status.status = sensor_msgs::msg::NavSatStatus::STATUS_FIX;
                        gps_msg.status.service = sensor_msgs::msg::NavSatStatus::SERVICE_GPS;
                        gps_msg.latitude = location.x;
                        gps_msg.longitude = location.y;
                        gps_msg.altitude = 0.0;
                        gps_publisher_->publish(gps_msg);
                        RCLCPP_INFO(this->get_logger(), "Published /rtos/gps: lat=%.6f lon=%.6f", gps_msg.latitude, gps_msg.longitude);
                        break;
                    }
                    case PublisherMessageType::Gear: {
                        Gear gear;
                        memcpy(&gear, &buffer[1], sizeof(gear));
                        std_msgs::msg::UInt8 gear_msg;
                        gear_msg.data = static_cast<uint8_t>(gear);
                        gear_publisher_->publish(gear_msg);
                        RCLCPP_INFO(this->get_logger(), "Published /rtos/gear = %u", gear_msg.data);
                        break;
                    }
                    default:
                        RCLCPP_WARN(this->get_logger(), "Invalid message type received: %d", static_cast<int>(message_type));
                        break;
                }
            }
        }

        close(sockfd);
    }

    rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr speed_publisher_;
    rclcpp::Publisher<std_msgs::msg::UInt8>::SharedPtr gear_publisher_;
    rclcpp::Publisher<sensor_msgs::msg::NavSatFix>::SharedPtr gps_publisher_;
    std::thread udp_thread_;
};

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<QNXPublisher>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
