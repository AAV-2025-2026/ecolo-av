
// basic headers that are needed when writing any publisher node
#include <chrono>
#include <functional>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/imu.hpp" // needed to use the IMU message type when building the message and sending it to the topic

using namespace std::chrono_literals; // needed to set specfici durations for certain functionalities, ROS2 only understands 
                                      // those setting those durations through chrono duration types

class QNXPublisher : public rclcpp::Node // public constructor, inherits everything from the Node class
{ 
                                          // used to build the node when you run the file
  public:
    QNXPublisher() : Node("test_Pub"), count_(0) // public constructor names the node "test_Pub" and initializes count_ to 0

    {
      publisher_ = this->create_publisher<sensor_msgs::msg::Imu>("qnx_imu", 10); // publisher initialized with IMU sensor message type
                                                                                // the name of the topic, "qnx_imu"
                                                                                // the limit amount of messages in the queue before we 
                                                                                  // start discarding messages
      timer_ = this->create_wall_timer(500ms, std::bind(&QNXPublisher::timer_callback, this)); // timer_ initialized,causing the 
                                                                                              // timer_callback to be executed twice
    }

  
  private:
    void timer_callback()
      {
        auto message = sensor_msgs::msg::Imu();

        message.header.stamp = this->get_clock()->now();
        message.header.frame_id = "imu_link";

        message.angular_velocity.x = static_cast<double>(std::rand() % 6);
        message.angular_velocity.y = static_cast<double>(std::rand() % 6); 
        message.angular_velocity.z = static_cast<double>(std::rand() % 6);
        message.linear_acceleration.x = static_cast<double>(std::rand() % 6);
        message.linear_acceleration.y = static_cast<double>(std::rand() % 6); 
        message.linear_acceleration.z = static_cast<double>(std::rand() % 6);

        RCLCPP_INFO(this->get_logger(), "Publishing IMU: %zu  |  angular_velocity = [%.2f,%.2f,%.2f] linear_acceleration = [%.2f,%.2f,%.2f]", 
        count_, message.angular_velocity.x, message.angular_velocity.y, message.angular_velocity.z, message.linear_acceleration.x, 
        message.linear_acceleration.y, message.linear_acceleration.z);

        publisher_->publish(message);
        count_++;
      }

      rclcpp::TimerBase::SharedPtr timer_;
      rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr publisher_;
      size_t count_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<QNXPublisher>());
  rclcpp::shutdown();
  return 0;

}