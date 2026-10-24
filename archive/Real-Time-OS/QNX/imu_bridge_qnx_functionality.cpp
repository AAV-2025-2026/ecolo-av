#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include <functional>



class QNX_sub_bridge: public rclcpp::Node
{
    public: 
        QNX_sub_bridge() : rclcpp::Node("qnx_sub_bridge"), seq(0)
        {
            const char * QNX_IP = "192.168.1.50" //Team mate QNX machine IP
            const int 
            sub_ = this->create_subscription<sensor_msgs::msg::Imu>("/imu/data", 10, 
                std::bind(&QNX_sub_bridge::sub_callback, this, std::placeholders::_1));
        }
        void sub_callback(const sensor_msgs::msg::Imu::SharedPtr sub_msg)
        {
            // Linear acceleration (m/s^2)
             double ax = sub_msg->linear_acceleration.x;
             double ay = sub_msg->linear_acceleration.y;
            double az = sub_msg->linear_acceleration.z;

            // Angular velocity / gyroscope (rad/s)
            double gx = sub_msg->angular_velocity.x;
            double gy = sub_msg->angular_velocity.y;
            double gz = sub_msg->angular_velocity.z;
            
        }

private:
      rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr sub_;

};

int main(int argc, char** argv){

    rclcpp::init(argc,argv); //initiliaze rclcpp with these arguments
    auto node = std::make_shared<QNX_sub_bridge>(); //making a node and passing it (first way of doing it)
    rclcpp::spin(node); //maintains a queue for the callback on this node
    rclcpp::shutdown();
    return 0;

}