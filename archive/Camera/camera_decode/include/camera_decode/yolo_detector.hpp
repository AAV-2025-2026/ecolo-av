#pragma once
#include <opencv2/opencv.hpp>
#include <NvInfer.h>
#include <NvInferRuntime.h>
#include <cuda_runtime_api.h>
#include <string>
#include <vector>

struct Detection {
    cv::Rect bbox;
    float    conf;
};

class TRTLogger : public nvinfer1::ILogger {
    void log(Severity s, const char* msg) noexcept override {
        if (s <= Severity::kWARNING)
            std::cerr << "[TRT] " << msg << "\n";
    }
};

class YoloDetector {
public:
    YoloDetector(const std::string& engine_path, float conf_thresh = 0.5f);
    ~YoloDetector();
    std::vector<Detection> detect(const cv::Mat& frame);

private:
    void preprocess(const cv::Mat& frame);
    std::vector<Detection> postprocess(int orig_w, int orig_h);

    TRTLogger logger_;
    nvinfer1::IRuntime*          runtime_  = nullptr;
    nvinfer1::ICudaEngine*       engine_   = nullptr;
    nvinfer1::IExecutionContext* context_  = nullptr;

    void*  gpu_buf_[2]  = {nullptr, nullptr};
    float* input_host_  = nullptr;
    float* output_host_ = nullptr;

    float conf_thresh_;
    static constexpr int INPUT_SIZE  = 640;
    static constexpr int NUM_DETS    = 8400;
    static constexpr int OUTPUT_VALS = 5;  // 4 bbox + 1 class
};
