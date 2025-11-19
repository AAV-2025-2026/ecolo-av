#include "camera_decode/nvdec_decoder_mmapi.hpp"
#include <iostream>
#include <stdexcept>
#include <cstring>

namespace camera_decode {

NvdecDecoderMmapi::NvdecDecoderMmapi(const std::string& rtsp_url)
    : rtsp_url_(rtsp_url)
    , is_opened_(false)
    , format_ctx_(nullptr)
    , packet_(nullptr)
    , video_stream_idx_(-1)
    , decoder_(nullptr)
    , frame_width_(0)
    , frame_height_(0)
    , dst_dmabuf_fd_(-1)
{
    av_log_set_level(AV_LOG_WARNING);

    if (!initRtspDemuxer()) {
        cleanup();
        throw std::runtime_error("Failed to initialize RTSP demuxer for URL: " + rtsp_url_);
    }

    if (!initDecoder()) {
        cleanup();
        throw std::runtime_error("Failed to initialize MMAPI decoder for URL: " + rtsp_url_);
    }

    is_opened_ = true;
    std::cout << "MMAPI Decoder initialized successfully for URL: " << rtsp_url_ << std::endl;
}

NvdecDecoderMmapi::~NvdecDecoderMmapi() {
    cleanup();
}

bool NvdecDecoderMmapi::initRtspDemuxer() {
    // Use FFmpeg only for RTSP demuxing and packet extraction
    AVDictionary* options = nullptr;
    av_dict_set(&options, "rtsp_transport", "udp", 0);
    av_dict_set(&options, "max_delay", "0", 0);
    av_dict_set(&options, "fflags", "nobuffer", 0);

    if (avformat_open_input(&format_ctx_, rtsp_url_.c_str(), nullptr, &options) < 0) {
        std::cerr << "Could not open input stream: " << rtsp_url_ << std::endl;
        av_dict_free(&options);
        return false;
    }
    av_dict_free(&options);

    if (avformat_find_stream_info(format_ctx_, nullptr) < 0) {
        std::cerr << "Could not find stream information." << std::endl;
        return false;
    }

    // Find video stream
    for (unsigned int i = 0; i < format_ctx_->nb_streams; i++) {
        if (format_ctx_->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
            video_stream_idx_ = i;
            break;
        }
    }

    if (video_stream_idx_ == -1) {
        std::cerr << "Could not find video stream." << std::endl;
        return false;
    }

    AVCodecParameters* codec_params = format_ctx_->streams[video_stream_idx_]->codecpar;
    frame_width_ = codec_params->width;
    frame_height_ = codec_params->height;

    packet_ = av_packet_alloc();
    if (!packet_) {
        std::cerr << "Could not allocate packet." << std::endl;
        return false;
    }

    return true;
}

bool NvdecDecoderMmapi::initDecoder() {
    int ret = 0;

    // Create MMAPI decoder
    decoder_ = NvVideoDecoder::createVideoDecoder("dec0");
    if (!decoder_) {
        std::cerr << "Could not create video decoder." << std::endl;
        return false;
    }

    // Set output plane format (decoded frames)
    ret = decoder_->setOutputPlaneFormat(V4L2_PIX_FMT_H264, frame_width_, frame_height_);
    if (ret < 0) {
        std::cerr << "Could not set output plane format." << std::endl;
        return false;
    }

    // Set capture plane format (NV12 output)
    ret = decoder_->setCapturePlaneFormat(V4L2_PIX_FMT_NV12M, frame_width_, frame_height_);
    if (ret < 0) {
        std::cerr << "Could not set capture plane format." << std::endl;
        return false;
    }

    // Setup buffers
    ret = decoder_->output_plane.setupPlane(V4L2_MEMORY_MMAP, 10, true, false);
    if (ret < 0) {
        std::cerr << "Could not setup output plane." << std::endl;
        return false;
    }

    ret = decoder_->capture_plane.setupPlane(V4L2_MEMORY_DMABUF, 10, true, false);
    if (ret < 0) {
        std::cerr << "Could not setup capture plane." << std::endl;
        return false;
    }

    // Start streaming
    ret = decoder_->output_plane.setStreamStatus(true);
    if (ret < 0) {
        std::cerr << "Could not start output plane streaming." << std::endl;
        return false;
    }

    ret = decoder_->capture_plane.setStreamStatus(true);
    if (ret < 0) {
        std::cerr << "Could not start capture plane streaming." << std::endl;
        return false;
    }

    // Create destination buffer for color conversion
    NvBufferCreateParams create_params = {0};
    create_params.width = frame_width_;
    create_params.height = frame_height_;
    create_params.layout = NvBufferLayout_Pitch;
    create_params.colorFormat = NvBufferColorFormat_ABGR32;
    create_params.payloadType = NvBufferPayload_SurfArray;
    create_params.nvbuf_tag = NvBufferTag_VIDEO_CONVERT;

    ret = NvBufferCreateEx(&dst_dmabuf_fd_, &create_params);
    if (ret < 0) {
        std::cerr << "Could not create destination buffer." << std::endl;
        return false;
    }

    return true;
}

void NvdecDecoderMmapi::cleanup() {
    if (decoder_) {
        delete decoder_;
        decoder_ = nullptr;
    }

    if (dst_dmabuf_fd_ != -1) {
        NvBufferDestroy(dst_dmabuf_fd_);
        dst_dmabuf_fd_ = -1;
    }

    if (packet_) {
        av_packet_free(&packet_);
    }

    if (format_ctx_) {
        avformat_close_input(&format_ctx_);
    }

    is_opened_ = false;
}

bool NvdecDecoderMmapi::isOpened() const {
    return is_opened_;
}

cv::Mat NvdecDecoderMmapi::getFrame() {
    cv::Mat output;

    if (!is_opened_) {
        return output;
    }

    // Read packet from RTSP stream using FFmpeg
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

bool NvdecDecoderMmapi::decodeFrame(cv::Mat& output) {
    // Get buffer from output plane
    struct v4l2_buffer v4l2_buf;
    struct v4l2_plane planes[MAX_PLANES];
    memset(&v4l2_buf, 0, sizeof(v4l2_buf));
    memset(planes, 0, sizeof(planes));
    v4l2_buf.m.planes = planes;

    NvBuffer* buffer = decoder_->output_plane.getNthBuffer(0);
    if (!buffer) {
        return false;
    }

    // Copy H.264 packet data to buffer
    buffer->planes[0].bytesused = packet_->size;
    memcpy(buffer->planes[0].data, packet_->data, packet_->size);

    // Queue buffer to decoder
    if (decoder_->output_plane.qBuffer(v4l2_buf, nullptr) < 0) {
        std::cerr << "Error queueing buffer to output plane." << std::endl;
        return false;
    }

    // Dequeue decoded frame from capture plane
    if (decoder_->capture_plane.dqBuffer(v4l2_buf, &buffer, nullptr, 0) < 0) {
        return false; // EAGAIN is normal
    }

    // Convert NvBuffer to cv::Mat
    if (!convertNvBufferToMat(buffer->planes[0].fd, output)) {
        return false;
    }

    // Queue buffer back to capture plane
    decoder_->capture_plane.qBuffer(v4l2_buf, nullptr);

    return true;
}

bool NvdecDecoderMmapi::convertNvBufferToMat(int src_dmabuf_fd, cv::Mat& output) {
    // Transform NV12 to ABGR using hardware
    NvBufferTransformParams transform_params;
    memset(&transform_params, 0, sizeof(transform_params));
    transform_params.transform_flag = NVBUFFER_TRANSFORM_FILTER;
    transform_params.transform_filter = NvBufferTransform_Filter_Smart;

    int ret = NvBufferTransform(src_dmabuf_fd, dst_dmabuf_fd_, &transform_params);
    if (ret < 0) {
        std::cerr << "Buffer transform failed." << std::endl;
        return false;
    }

    // Map buffer to CPU memory
    void* pdata = nullptr;
    NvBufferParams params;
    NvBufferGetParams(dst_dmabuf_fd_, &params);
    
    ret = NvBufferMemMap(dst_dmabuf_fd_, 0, NvBufferMem_Read, &pdata);
    if (ret < 0) {
        std::cerr << "Buffer map failed." << std::endl;
        return false;
    }

    NvBufferMemSyncForCpu(dst_dmabuf_fd_, 0, &pdata);

    // Create cv::Mat (ABGR -> BGR conversion)
    cv::Mat imgbuf(frame_height_, frame_width_, CV_8UC4, pdata, params.pitch[0]);
    cv::cvtColor(imgbuf, output, cv::COLOR_RGBA2BGR);

    // Unmap buffer
    NvBufferMemUnMap(dst_dmabuf_fd_, 0, &pdata);

    return true;
}

} // namespace camera_decode
