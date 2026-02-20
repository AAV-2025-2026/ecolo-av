#ifndef CAMERA_DECODE_NVDEC_DECODER_HPP
#define CAMERA_DECODE_NVDEC_DECODER_HPP

#include <string>
#include <opencv2/opencv.hpp>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libavutil/imgutils.h>
#include <libswscale/swscale.h>
}

namespace camera_decode {

    class NvDecDecoder {
    public:
        explicit NvDecDecoder(const std::string& rtsp_url);
        ~NvDecDecoder();
        
        bool isOpened() const;
        cv::Mat getFrame();

    private:
        bool initDecoder();
        void cleanup();
        bool decodeFrame(cv::Mat& output);

        std::string rtsp_url_;
        bool is_opened_;
        
        AVFormatContext* format_ctx_;
        AVCodecContext* codec_ctx_;
        const AVCodec* codec_;
        AVFrame* frame_;
        AVFrame* frame_bgr_;
        AVPacket* packet_;
        SwsContext* sws_ctx_;
        
        int video_stream_idx_;
        int frame_width_;
        int frame_height_;
    };

} // namespace camera_decode

#endif // CAMERA_DECODE_NVDEC_DECODER_HPP
