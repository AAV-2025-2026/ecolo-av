#include <iostream>
#include <stdexcept>
#include "camera_decode/nvdec_decoder.hpp"

namespace camera_decode {
    NvDecDecoder::NvDecDecoder(const std::string& rtsp_url)
    : rtsp_url_(rtsp_url)
    , is_opened_(false)
    , format_ctx_(nullptr)
    , codec_ctx_(nullptr)
    , codec_(nullptr)
    , frame_(nullptr)
    , frame_bgr_(nullptr)
    , packet_(nullptr)
    , sws_ctx_(nullptr)
    , video_stream_idx_(-1)
    , frame_width_(0)
    , frame_height_(0)
    {
        av_log_set_level(AV_LOG_WARNING); // Set FFMPEG log level to warning

        if (!initDecoder()) {
            cleanup();
            throw std::runtime_error("Failed to initialize NVDEC decoder for URL: " + rtsp_url_);
        }

        is_opened_ = true;
        std::cout << "NVDEC Decoder initialized successfully for URL: " << rtsp_url_ << std::endl;
    }

    NvDecDecoder::~NvDecDecoder() {
        cleanup();
    }

    bool NvDecDecoder::initDecoder(){

        // Set FFMPEG options for RTSP over UDP
        AVDictionary* options = nullptr;
        av_dict_set(&options, "rtsp_transport", "udp", 0);      // Use UDP transport
        av_dict_set(&options, "max_delay", "0", 0);             // No delay
        av_dict_set(&options, "fflags", "nobuffer", 0);         // No buffering

        av_dict_set(&options, "flags",          "low_delay", 0); 
        av_dict_set(&options, "stimeout",       "1000000", 0);    // 1s timeout
        av_dict_set(&options, "probesize",      "32", 0);         // min probe
        av_dict_set(&options, "analyzeduration","0", 0);          // skip analysis

        // Try to open the input stream
        if (avformat_open_input(&format_ctx_, rtsp_url_.c_str(), nullptr, &options) < 0) {
            std::cerr << "Could not open input stream: " << rtsp_url_ << std::endl;
            av_dict_free(&options);
            return false;
        }
        av_dict_free(&options);

        if(avformat_find_stream_info(format_ctx_, nullptr) < 0) {
            std::cerr << "Could not find stream information." << std::endl;
            return false;
        }

        // Find the first video stream
        video_stream_idx_ = -1;
        for (unsigned int i = 0; i < format_ctx_->nb_streams; i++) {
            if (format_ctx_->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
                video_stream_idx_ = i;
                break;
            }
        }

        if (video_stream_idx_ == -1) {
            std::cerr << "Could not find a video stream in the input." << std::endl;
            return false;
        }

        // Get codec parameters
        AVCodecParameters* codec_params = format_ctx_->streams[video_stream_idx_]->codecpar;
        frame_width_ = codec_params->width;
        frame_height_ = codec_params->height;

        // Find the decoder for the video stream
        codec_ = avcodec_find_decoder_by_name("h264_nvv4l2dec");
        if (!codec_)
        {
            std::cerr << "NVDEC decoder not available, falling back to software decoder." << std::endl;
            codec_ = avcodec_find_decoder(codec_params->codec_id);
        }

        // Check if codec is found
        if (!codec_) {
            std::cerr << "Unsupported codec!" << std::endl;
            return false;
        }

        // Allocate codec context
        codec_ctx_ = avcodec_alloc_context3(codec_);
        if (!codec_ctx_) {
            std::cerr << "Could not allocate codec context." << std::endl;
            return false;
        }

        // Copy codec parameters to context
        if (avcodec_parameters_to_context(codec_ctx_, codec_params) < 0) {
            std::cerr << "Could not copy codec parameters to context." << std::endl;
            return false;
        }

        // Open codec
        if (avcodec_open2(codec_ctx_, codec_, nullptr) < 0) {
            std::cerr << "Could not open codec." << std::endl;
            return false;
        }

        frame_ = av_frame_alloc();
        frame_bgr_ = av_frame_alloc();
        if (!frame_ || !frame_bgr_) {
            std::cerr << "Could not allocate frames." << std::endl;
            return false;
        }

        int num_bytes = av_image_get_buffer_size(AV_PIX_FMT_BGR24, frame_width_, frame_height_, 1);
        uint8_t* buffer = (uint8_t*)av_malloc(num_bytes * sizeof(uint8_t));
        av_image_fill_arrays(frame_bgr_->data, frame_bgr_->linesize, buffer, AV_PIX_FMT_BGR24, frame_width_, frame_height_, 1);

        sws_ctx_ = sws_getContext(frame_width_, frame_height_, codec_ctx_->pix_fmt,
                                    frame_width_, frame_height_, AV_PIX_FMT_BGR24,
                                    SWS_BILINEAR, nullptr, nullptr, nullptr);

        // Check if sws_ctx_ is initialized
        if (!sws_ctx_) {
            std::cerr << "Could not initialize SwsContext." << std::endl;
            return false;
        }

        // Allocate packet
        packet_ = av_packet_alloc();
        if (!packet_) {
            std::cerr << "Could not allocate AVPacket." << std::endl;
            return false;
        }

        return true;
    }

    void NvDecDecoder::cleanup() {
        // Free allocated resources
        if (sws_ctx_) {
            sws_freeContext(sws_ctx_);
            sws_ctx_ = nullptr;
        }
        
        if (frame_bgr_) {
            if (frame_bgr_->data[0]) {
                av_free(frame_bgr_->data[0]);
            }
            av_frame_free(&frame_bgr_);
        }
        
        if (frame_) {
            av_frame_free(&frame_);
        }
        
        if (packet_) {
            av_packet_free(&packet_);
        }
        
        if (codec_ctx_) {
            avcodec_free_context(&codec_ctx_);
        }
        
        if (format_ctx_) {
            avformat_close_input(&format_ctx_);
        }
        
        is_opened_ = false;
    }

    // Check if the decoder is opened
    bool NvDecDecoder::isOpened() const {
        return is_opened_;
    }

    // Get a decoded frame as cv::Mat
    cv::Mat NvDecDecoder::getFrame() {
        cv::Mat output;
        
        if (!is_opened_) {
            return output;
        }
        
        // Read frames from the stream
        while (av_read_frame(format_ctx_, packet_) >= 0) {
            if (packet_->stream_index == video_stream_idx_) {
                if (decodeFrame(output)) {
                    av_packet_unref(packet_);
                    return output;
                }
            }
            av_packet_unref(packet_);
        }
        
        return output;
    }

    bool NvDecDecoder::decodeFrame(cv::Mat& output) {
        // Send packet to decoder
        int ret = avcodec_send_packet(codec_ctx_, packet_);
        if (ret < 0) {
            std::cerr << "Error sending packet to decoder" << std::endl;
            return false;
        }
        
        // Receive frame from decoder
        ret = avcodec_receive_frame(codec_ctx_, frame_);
        if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) {
            return false;
        } else if (ret < 0) {
            std::cerr << "Error receiving frame from decoder" << std::endl;
            return false;
        }
        
        // Convert the frame to BGR format
        sws_scale(
            sws_ctx_,
            frame_->data, frame_->linesize, 0, frame_height_,
            frame_bgr_->data, frame_bgr_->linesize
        );

        // Create cv::Mat from the converted frame
        output = cv::Mat(frame_height_, frame_width_, CV_8UC3, frame_bgr_->data[0]).clone();
        
        return true;
    }

} // namespace camera_decode
