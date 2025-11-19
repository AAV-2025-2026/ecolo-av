#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <cv_bridge/cv_bridge.h>
#include "camera_decode/nvdec_decoder.hpp"

// Camera Decode Node
class CameraDecodeNode : public rclcpp::Node {
public:
    // Constructor
    CameraDecodeNode() : Node("camera_decode_node") {
        this->declare_parameter("camera_name", "cam1");
        this->declare_parameter("rtsp_url", "rtsp://192.168.1.101:8554/cam1");
        this->declare_parameter("frame_rate", 30);
        
        // Get parameters
        camera_name_ = this->get_parameter("camera_name").as_string();
        std::string rtsp_url = this->get_parameter("rtsp_url").as_string();
        int frame_rate = this->get_parameter("frame_rate").as_int();
        
        // Initialize decoder
        RCLCPP_INFO(this->get_logger(), "Initializing camera: %s", camera_name_.c_str());
        RCLCPP_INFO(this->get_logger(), "RTSP URL: %s", rtsp_url.c_str());
        
        // Create NVDEC decoder instance
        try {
            decoder_ = std::make_unique<camera_decode::NvDecDecoder>(rtsp_url);
        } catch (const std::exception& e) {
            RCLCPP_ERROR(this->get_logger(), "Failed to initialize decoder: %s", e.what());
            rclcpp::shutdown();
            return;
        }
        
        //  Create image publisher
        std::string topic_name = "/camera/" + camera_name_ + "/image_raw";
        image_pub_ = this->create_publisher<sensor_msgs::msg::Image>(topic_name, 10);
        
        // Create timer for frame publishing
        auto timer_period = std::chrono::milliseconds(1000 / frame_rate);
        timer_ = this->create_wall_timer(
            timer_period,
            std::bind(&CameraDecodeNode::timer_callback, this));
        
        RCLCPP_INFO(this->get_logger(), "Camera decode node started: %s", camera_name_.c_str());
    }

private:
    // Timer callback to fetch and publish frames
    void timer_callback() {
        cv::Mat frame = decoder_->getFrame();
        
        if (frame.empty()) {
            RCLCPP_WARN_THROTTLE(this->get_logger(), *this->get_clock(), 1000,
                                    "Empty frame received from %s", camera_name_.c_str());
            return;
        }
        
        // Publish the frame
        std_msgs::msg::Header header;
        header.stamp = this->now();
        header.frame_id = camera_name_;
        
        // Convert cv::Mat to ROS Image message and publish
        auto msg = cv_bridge::CvImage(header, "bgr8", frame).toImageMsg();
        image_pub_->publish(*msg);
        
        // Log publishing info
        RCLCPP_DEBUG_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                                "Published frame from %s [%dx%d]",
                                camera_name_.c_str(), frame.cols, frame.rows);
    }

    // Member variables
    std::string camera_name_;
    std::unique_ptr<camera_decode::NvDecDecoder> decoder_;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image_pub_;
    rclcpp::TimerBase::SharedPtr timer_;
};

// Main function
int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<CameraDecodeNode>());
    rclcpp::shutdown();
    return 0;
}