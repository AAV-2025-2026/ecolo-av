#pragma once

#include <string>
#include <memory>
#include <opencv2/opencv.hpp>
#include "NvVideoDecoder.h"
#include "NvBuffer.h"
#include "NvUtils.h"

extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
}

namespace camera_decode {

class NvdecDecoderMmapi {
public:
    explicit NvdecDecoderMmapi(const std::string& rtsp_url);
    ~NvdecDecoderMmapi();

    bool isOpened() const;
    cv::Mat getFrame();

private:
    bool initDecoder();
    bool initRtspDemuxer();
    void cleanup();
    bool decodeFrame(cv::Mat& output);
    bool convertNvBufferToMat(int dmabuf_fd, cv::Mat& output);

    std::string rtsp_url_;
    bool is_opened_;
    
    // FFmpeg for RTSP demuxing only
    AVFormatContext* format_ctx_;
    AVPacket* packet_;
    int video_stream_idx_;
    
    // MMAPI decoder
    NvVideoDecoder* decoder_;
    int frame_width_;
    int frame_height_;
    
    // Buffer for color conversion
    int dst_dmabuf_fd_;
};

} // namespace camera_decode
