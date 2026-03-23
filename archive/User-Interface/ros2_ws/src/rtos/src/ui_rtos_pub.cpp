#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"

using namespace std::chrono_literals;

class QNXPublisher : public rclcpp::Node
{
public:
    QNXPublisher() : Node("qnx_udp_imu_pub")
    {
        publisher_ = this->create_publisher<sensor_msgs::msg::Imu>("qnx_imu", 10);

        // Starts UDP listener thread
        udp_thread_ = std::thread(&QNXPublisher::udp_listener, this);
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
                // Parses UDP payload into IMU data
                // Assuming UDP data is 6 floats in ASCII: ax ay az gx gy gz
                double ax, ay, az, gx, gy, gz;
                int n = sscanf(buffer, "%lf %lf %lf %lf %lf %lf", &ax, &ay, &az, &gx, &gy, &gz);
                if (n == 6) {
                    auto msg = sensor_msgs::msg::Imu();
                    msg.header.stamp = this->get_clock()->now();
                    msg.header.frame_id = "imu_link";

                    msg.linear_acceleration.x = ax;
                    msg.linear_acceleration.y = ay;
                    msg.linear_acceleration.z = az;

                    msg.angular_velocity.x = gx;
                    msg.angular_velocity.y = gy;
                    msg.angular_velocity.z = gz;

                    publisher_->publish(msg);

                    RCLCPP_INFO(this->get_logger(),
                                "Published IMU | linear_accel=[%.2f, %.2f, %.2f] "
                                "angular_vel=[%.2f, %.2f, %.2f]",
                                ax, ay, az, gx, gy, gz);
                }
            }
        }

        close(sockfd);
    }

    rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr publisher_;
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