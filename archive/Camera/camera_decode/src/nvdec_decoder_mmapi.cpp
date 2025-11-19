#include "camera_decode/nvdec_decoder_mmapi.hpp"

#include <iostream>
#include <stdexcept>
#include <cstring>

extern "C" {
#include <libavutil/log.h>
}

#include "nvbufsurftransform.h"

namespace camera_decode
{

NvdecDecoderMmapi::NvdecDecoderMmapi(const std::string &rtsp_url)
    : rtsp_url_(rtsp_url),
      is_opened_(false),
      format_ctx_(nullptr),
      packet_(nullptr),
      video_stream_idx_(-1),
      frame_width_(0),
      frame_height_(0),
      decoder_(nullptr),
      dst_surf_(nullptr),
      dst_dmabuf_fd_(-1),
      packets_fed_(0),
      capture_plane_setup_(false)
{
    av_log_set_level(AV_LOG_WARNING);

    std::cout << "Initializing RTSP demuxer..." << std::endl;
    if (!initRtspDemuxer()) {
        cleanup();
        throw std::runtime_error("Failed to initialize RTSP demuxer for URL: " + rtsp_url_);
    }

    std::cout << "Initializing MMAPI decoder..." << std::endl;
    if (!initDecoder()) {
        cleanup();
        throw std::runtime_error("Failed to initialize MMAPI decoder for URL: " + rtsp_url_);
    }

    is_opened_ = true;
    std::cout << "MMAPI Decoder initialized successfully for URL: " << rtsp_url_ << std::endl;
}

NvdecDecoderMmapi::~NvdecDecoderMmapi()
{
    cleanup();
}

bool NvdecDecoderMmapi::initRtspDemuxer()
{
    AVDictionary *options = nullptr;
    av_dict_set(&options, "rtsp_transport", "tcp", 0);
    av_dict_set(&options, "max_delay", "500000", 0);
    av_dict_set(&options, "fflags", "nobuffer", 0);
    av_dict_set(&options, "stimeout", "5000000", 0);  // 5s

    std::cout << "Opening RTSP stream: " << rtsp_url_ << std::endl;
    if (avformat_open_input(&format_ctx_, rtsp_url_.c_str(), nullptr, &options) < 0) {
        std::cerr << "Could not open input stream: " << rtsp_url_ << std::endl;
        av_dict_free(&options);
        return false;
    }
    av_dict_free(&options);

    std::cout << "Finding stream info..." << std::endl;
    if (avformat_find_stream_info(format_ctx_, nullptr) < 0) {
        std::cerr << "Could not find stream information." << std::endl;
        return false;
    }

    // Find video stream
    for (unsigned int i = 0; i < format_ctx_->nb_streams; ++i) {
        if (format_ctx_->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
            video_stream_idx_ = static_cast<int>(i);
            break;
        }
    }

    if (video_stream_idx_ == -1) {
        std::cerr << "Could not find video stream." << std::endl;
        return false;
    }

    AVCodecParameters *codec_params = format_ctx_->streams[video_stream_idx_]->codecpar;
    frame_width_ = codec_params->width;
    frame_height_ = codec_params->height;

    std::cout << "Video stream found: " << frame_width_ << "x" << frame_height_ << std::endl;

    packet_ = av_packet_alloc();
    if (!packet_) {
        std::cerr << "Could not allocate packet." << std::endl;
        return false;
    }

    return true;
}

bool NvdecDecoderMmapi::initDecoder()
{
    std::cout << "Creating video decoder..." << std::endl;

    static int decoder_num = 0;
    char       dec_name[16];
    std::snprintf(dec_name, sizeof(dec_name), "dec%d", decoder_num++);

    decoder_ = NvVideoDecoder::createVideoDecoder(dec_name);
    if (!decoder_) {
        std::cerr << "Could not create video decoder " << dec_name << std::endl;
        return false;
    }

    std::cout << "Video decoder " << dec_name << " created successfully" << std::endl;

    // Set output plane format first (encoded H.264)
    std::cout << "Setting output plane format..." << std::endl;
    int ret = decoder_->setOutputPlaneFormat(V4L2_PIX_FMT_H264, 0);
    if (ret < 0) {
        std::cerr << "Could not set output plane format." << std::endl;
        return false;
    }

    // Optional: disable DPB
    ret = decoder_->disableDPB();
    if (ret < 0) {
        std::cout << "Warning: Could not disable DPB" << std::endl;
    }

    // Setup output plane buffers
    std::cout << "Setting up output plane buffers..." << std::endl;
    ret = decoder_->output_plane.setupPlane(V4L2_MEMORY_MMAP, 10, true, false);
    if (ret < 0) {
        std::cerr << "Could not setup output plane." << std::endl;
        return false;
    }

    // Start output plane streaming
    std::cout << "Starting output plane streaming..." << std::endl;
    ret = decoder_->output_plane.setStreamStatus(true);
    if (ret < 0) {
        std::cerr << "Could not start output plane streaming." << std::endl;
        return false;
    }

    // Subscribe to resolution change
    std::cout << "Subscribing to V4L2 events..." << std::endl;
    ret = decoder_->subscribeEvent(V4L2_EVENT_RESOLUTION_CHANGE, 0, 0);
    if (ret < 0) {
        std::cerr << "Could not subscribe to V4L2_EVENT_RESOLUTION_CHANGE." << std::endl;
        return false;
    }

    std::cout << "Decoder initialization complete - capture plane will be set up after first frames"
              << std::endl;
    return true;
}

void NvdecDecoderMmapi::cleanup()
{
    if (decoder_) {
        decoder_->abort();
        delete decoder_;
        decoder_ = nullptr;
    }

    if (dst_surf_) {
        NvBufSurfaceDestroy(dst_surf_);
        dst_surf_ = nullptr;
        dst_dmabuf_fd_ = -1;
    }

    if (packet_) {
        av_packet_free(&packet_);
    }

    if (format_ctx_) {
        avformat_close_input(&format_ctx_);
        format_ctx_ = nullptr;
    }

    is_opened_ = false;
}

bool NvdecDecoderMmapi::isOpened() const
{
    return is_opened_;
}

cv::Mat NvdecDecoderMmapi::getFrame()
{
    cv::Mat output;

    if (!is_opened_) {
        return output;
    }

    constexpr int max_attempts = 50;

    for (int attempt = 0; attempt < max_attempts; ++attempt) {
        int read_ret = av_read_frame(format_ctx_, packet_);
        if (read_ret < 0) {
            std::cerr << "Error reading frame or end of stream" << std::endl;
            return cv::Mat();
        }

        if (packet_->stream_index != video_stream_idx_) {
            av_packet_unref(packet_);
            continue;
        }

        if (decodeFrame(output)) {
            av_packet_unref(packet_);
            return output;
        }

        av_packet_unref(packet_);
    }

    return cv::Mat();
}

bool NvdecDecoderMmapi::decodeFrame(cv::Mat &output)
{
    if (!feedPacketToDecoder()) {
        return false;
    }

    return getDecodedFrame(output);
}

bool NvdecDecoderMmapi::feedPacketToDecoder()
{
    struct v4l2_buffer v4l2_buf;
    struct v4l2_plane  planes[MAX_PLANES];

    std::memset(&v4l2_buf, 0, sizeof(v4l2_buf));
    std::memset(planes, 0, sizeof(planes));

    v4l2_buf.type   = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
    v4l2_buf.memory = V4L2_MEMORY_MMAP;
    v4l2_buf.m.planes = planes;
    v4l2_buf.length   = 1;

    int ret = decoder_->output_plane.dqBuffer(v4l2_buf, nullptr, nullptr, 10);
    if (ret < 0) {
        return false;
    }

    NvBuffer *buffer = decoder_->output_plane.getNthBuffer(v4l2_buf.index);
    if (!buffer || static_cast<uint32_t>(packet_->size) > buffer->planes[0].length) {
        decoder_->output_plane.qBuffer(v4l2_buf, nullptr);
        return false;
    }

    std::memcpy(buffer->planes[0].data, packet_->data, packet_->size);
    v4l2_buf.m.planes[0].bytesused = packet_->size;

    ++packets_fed_;
    if (packets_fed_ % 30 == 0) {
        std::cout << "Fed " << packets_fed_ << " packets to decoder" << std::endl;
    }

    ret = decoder_->output_plane.qBuffer(v4l2_buf, nullptr);
    return (ret >= 0);
}

bool NvdecDecoderMmapi::getDecodedFrame(cv::Mat &output)
{
    if (!capture_plane_setup_) {
        struct v4l2_event ev;
        int               ret = decoder_->dqEvent(ev, 0);

        if (ret == 0 && ev.type == V4L2_EVENT_RESOLUTION_CHANGE) {
            std::cout << "Got resolution change event, setting up capture plane..." << std::endl;
            if (!setupCapturePlane()) {
                std::cerr << "Failed to setup capture plane after resolution change" << std::endl;
                return false;
            }
            capture_plane_setup_ = true;
            std::cout << "Capture plane setup successful!" << std::endl;
        } else if (packets_fed_ >= 30 && !capture_plane_setup_) {
            std::cout << "Forcing capture plane setup after " << packets_fed_
                      << " packets (no event received)..." << std::endl;

            struct v4l2_format format;
            std::memset(&format, 0, sizeof(format));
            format.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;

            if (decoder_->capture_plane.getFormat(format) == 0) {
                frame_width_  = format.fmt.pix_mp.width;
                frame_height_ = format.fmt.pix_mp.height;
                std::cout << "Queried resolution: " << frame_width_ << "x"
                          << frame_height_ << std::endl;
            }

            if (!setupCapturePlane()) {
                std::cerr << "Failed to force setup capture plane" << std::endl;
                return false;
            }

            capture_plane_setup_ = true;
            std::cout << "Forced capture plane setup successful!" << std::endl;
        } else {
            return false;
        }
    }

    if (!capture_plane_setup_ || !decoder_->capture_plane.getNumBuffers()) {
        return false;
    }

    struct v4l2_buffer cap_v4l2_buf;
    struct v4l2_plane  cap_planes[MAX_PLANES];
    NvBuffer          *cap_buffer = nullptr;

    std::memset(&cap_v4l2_buf, 0, sizeof(cap_v4l2_buf));
    std::memset(cap_planes, 0, sizeof(cap_planes));

    cap_v4l2_buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
    cap_v4l2_buf.memory = V4L2_MEMORY_MMAP;
    cap_v4l2_buf.m.planes = cap_planes;
    cap_v4l2_buf.length   = 2;

    int ret = decoder_->capture_plane.dqBuffer(cap_v4l2_buf, &cap_buffer, nullptr, 0);
    if (ret < 0 || !cap_buffer) {
        return false;
    }

    static int frame_count = 0;
    ++frame_count;

    if (frame_count == 1) {
        std::cout << "Got first decoded frame!" << std::endl;
    } else if (frame_count % 100 == 0) {
        std::cout << "Decoded " << frame_count << " frames" << std::endl;
    }

    bool ok = convertNvBufferToMat(cap_buffer->planes[0].fd, output);

    decoder_->capture_plane.qBuffer(cap_v4l2_buf, nullptr);

    return ok;
}

bool NvdecDecoderMmapi::setupCapturePlane()
{
    int ret = decoder_->setCapturePlaneFormat(V4L2_PIX_FMT_NV12M, frame_width_, frame_height_);
    if (ret < 0) {
        std::cerr << "Could not set capture plane format" << std::endl;
        return false;
    }

    ret = decoder_->capture_plane.setupPlane(V4L2_MEMORY_MMAP, 6, true, false);
    if (ret < 0) {
        std::cerr << "Could not setup capture plane" << std::endl;
        return false;
    }

    ret = decoder_->capture_plane.setStreamStatus(true);
    if (ret < 0) {
        std::cerr << "Could not start capture plane streaming" << std::endl;
        return false;
    }

    for (uint32_t i = 0; i < decoder_->capture_plane.getNumBuffers(); ++i) {
        struct v4l2_buffer v4l2_buf;
        struct v4l2_plane  planes[MAX_PLANES];

        std::memset(&v4l2_buf, 0, sizeof(v4l2_buf));
        std::memset(planes, 0, sizeof(planes));

        v4l2_buf.index   = i;
        v4l2_buf.type    = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
        v4l2_buf.memory  = V4L2_MEMORY_MMAP;
        v4l2_buf.m.planes = planes;
        v4l2_buf.length   = 2;

        ret = decoder_->capture_plane.qBuffer(v4l2_buf, nullptr);
        if (ret < 0) {
            std::cerr << "Could not queue capture buffer " << i << std::endl;
            return false;
        }
    }

    if (!dst_surf_) {
        NvBufSurfaceCreateParams create_params;
        std::memset(&create_params, 0, sizeof(create_params));

        create_params.gpuId        = 0;
        create_params.width        = frame_width_;
        create_params.height       = frame_height_;
        create_params.size         = 0;
        create_params.isContiguous = true;
        create_params.colorFormat  = NVBUF_COLOR_FORMAT_ABGR;
        create_params.layout       = NVBUF_LAYOUT_PITCH;
        create_params.memType      = NVBUF_MEM_SURFACE_ARRAY;

        ret = NvBufSurfaceCreate(&dst_surf_, 1, &create_params);
        if (ret < 0) {
            std::cerr << "Could not create destination buffer surface" << std::endl;
            return false;
        }

        ret = NvBufSurfaceMapEglImage(dst_surf_, 0);
        if (ret < 0) {
            std::cerr << "Could not map EGL image" << std::endl;
            return false;
        }

        dst_dmabuf_fd_ = dst_surf_->surfaceList[0].bufferDesc;
    }

    std::cout << "Capture plane setup complete" << std::endl;
    return true;
}

bool NvdecDecoderMmapi::convertNvBufferToMat(int src_dmabuf_fd, cv::Mat &output)
{
    NvBufSurfTransformParams transform_params;
    std::memset(&transform_params, 0, sizeof(transform_params));

    transform_params.transform_flag   = NVBUFSURF_TRANSFORM_FILTER;
    transform_params.transform_filter = NvBufSurfTransformInter_Default;

    NvBufSurface *src_surf = nullptr;
    int           ret      = NvBufSurfaceFromFd(src_dmabuf_fd,
                                               reinterpret_cast<void **>(&src_surf));
    if (ret < 0) {
        std::cerr << "Failed to get surface from fd" << std::endl;
        return false;
    }

    ret = NvBufSurfTransform(src_surf, dst_surf_, &transform_params);
    if (ret < 0) {
        std::cerr << "Failed to transform surface" << std::endl;
        return false;
    }

    ret = NvBufSurfaceMap(dst_surf_, 0, 0, NVBUF_MAP_READ);
    if (ret < 0) {
        std::cerr << "Failed to map surface" << std::endl;
        return false;
    }

    NvBufSurfaceSyncForCpu(dst_surf_, 0, 0);

    void    *pdata = dst_surf_->surfaceList[0].mappedAddr.addr[0];
    uint32_t pitch = dst_surf_->surfaceList[0].pitch;

    if (!pdata) {
        std::cerr << "Mapped address is null" << std::endl;
        NvBufSurfaceUnMap(dst_surf_, 0, 0);
        return false;
    }

    cv::Mat rgba(frame_height_, frame_width_, CV_8UC4, pdata, pitch);
    cv::cvtColor(rgba, output, cv::COLOR_RGBA2BGR);

    NvBufSurfaceUnMap(dst_surf_, 0, 0);

    return true;
}

}  // namespace camera_decode
