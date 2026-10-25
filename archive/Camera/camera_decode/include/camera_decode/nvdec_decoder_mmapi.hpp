#pragma once

#include <string>
#include <memory>

extern "C" {
#include <libavformat/avformat.h>
}

#include <opencv2/opencv.hpp>

#include "NvVideoDecoder.h"
#include "nvbufsurface.h"

namespace camera_decode
{

class NvdecDecoderMmapi
{
public:
    explicit NvdecDecoderMmapi(const std::string &rtsp_url);
    ~NvdecDecoderMmapi();

    bool isOpened() const;

    // Get one decoded frame; empty Mat if none available yet
    cv::Mat getFrame();

private:
    bool initRtspDemuxer();
    bool initDecoder();

    bool decodeFrame(cv::Mat &output);
    bool feedPacketToDecoder();
    bool getDecodedFrame(cv::Mat &output);

    bool setupCapturePlane();
    bool convertNvBufferToMat(int src_dmabuf_fd, cv::Mat &output);

    void cleanup();

private:
    std::string rtsp_url_;
    bool        is_opened_;

    // FFmpeg RTSP demux
    AVFormatContext *format_ctx_;
    AVPacket        *packet_;
    int              video_stream_idx_;
    int              frame_width_;
    int              frame_height_;

    // MMAPI decoder
    NvVideoDecoder *decoder_;

    // Color conversion surface (NV12 -> RGBA -> BGR)
    NvBufSurface *dst_surf_;
    int           dst_dmabuf_fd_;

    // State
    int  packets_fed_;
    bool capture_plane_setup_;
};

}  // namespace camera_decode
