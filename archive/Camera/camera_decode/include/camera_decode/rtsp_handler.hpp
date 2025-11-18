#ifndef CAMERA_DECODE_RTSP_HANDLER_HPP
#define CAMERA_DECODE_RTSP_HANDLER_HPP

#include <string>
#include <opencv2/opencv.hpp>

namespace camera_decode {
    class RtspHandler {
        public:
            explicit RtspHandler(const std::string& rtsp_url);
            ~RtspHandler();

            bool isOpened() const;
            cv::Mat getFrame();

        private:
            cv::VideoCapture cap_;
            std::string rtsp_url_;
    };

} // CAMERA_DECODE_RTSP_HANDLER_HPP

#endif // CAMERA_DECODE_RTSP_HANDLER_HPP