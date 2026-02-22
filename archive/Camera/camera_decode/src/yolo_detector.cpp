#include "camera_decode/yolo_detector.hpp"
#include <fstream>
#include <stdexcept>

YoloDetector::YoloDetector(const std::string& engine_path, float conf_thresh)
    : conf_thresh_(conf_thresh)
{
    std::ifstream f(engine_path, std::ios::binary);
    if (!f) throw std::runtime_error("Cannot open engine: " + engine_path);
    f.seekg(0, std::ios::end);
    size_t sz = f.tellg(); f.seekg(0);
    std::vector<char> data(sz);
    f.read(data.data(), sz);

    runtime_ = nvinfer1::createInferRuntime(logger_);
    engine_  = runtime_->deserializeCudaEngine(data.data(), sz);
    context_ = engine_->createExecutionContext();

    cudaMalloc(&gpu_buf_[0], 3 * INPUT_SIZE * INPUT_SIZE * sizeof(float));
    cudaMalloc(&gpu_buf_[1], OUTPUT_VALS * NUM_DETS * sizeof(float));
    input_host_  = new float[3 * INPUT_SIZE * INPUT_SIZE];
    output_host_ = new float[OUTPUT_VALS * NUM_DETS];
}

YoloDetector::~YoloDetector() {
    cudaFree(gpu_buf_[0]);
    cudaFree(gpu_buf_[1]);
    delete[] input_host_;
    delete[] output_host_;
    delete context_;
    delete engine_;
    delete runtime_;
}

void YoloDetector::preprocess(const cv::Mat& frame) {
    cv::Mat resized, rgb;
    cv::resize(frame, resized, {INPUT_SIZE, INPUT_SIZE});
    cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);
    rgb.convertTo(rgb, CV_32FC3, 1.0f / 255.0f);

    std::vector<cv::Mat> ch(3);
    cv::split(rgb, ch);
    int plane = INPUT_SIZE * INPUT_SIZE;
    for (int c = 0; c < 3; ++c)
        memcpy(input_host_ + c * plane, ch[c].data, plane * sizeof(float));

    cudaMemcpy(gpu_buf_[0], input_host_,
               3 * plane * sizeof(float), cudaMemcpyHostToDevice);
}

std::vector<Detection> YoloDetector::postprocess(int orig_w, int orig_h) {
    cudaMemcpy(output_host_, gpu_buf_[1],
               OUTPUT_VALS * NUM_DETS * sizeof(float), cudaMemcpyDeviceToHost);

    float sx = (float)orig_w / INPUT_SIZE;
    float sy = (float)orig_h / INPUT_SIZE;

    std::vector<cv::Rect> boxes;
    std::vector<float>    scores;

    for (int i = 0; i < NUM_DETS; ++i) {
        float score = output_host_[4 * NUM_DETS + i];
        if (score < conf_thresh_) continue;

        float cx = output_host_[0 * NUM_DETS + i];
        float cy = output_host_[1 * NUM_DETS + i];
        float w  = output_host_[2 * NUM_DETS + i];
        float h  = output_host_[3 * NUM_DETS + i];

        int x1 = (int)((cx - w / 2.0f) * sx);
        int y1 = (int)((cy - h / 2.0f) * sy);
        int bw = (int)(w * sx);
        int bh = (int)(h * sy);

        boxes.push_back({x1, y1, bw, bh});
        scores.push_back(score);
    }

    // NMS
    std::vector<int> indices;
    cv::dnn::NMSBoxes(boxes, scores, conf_thresh_, 0.45f, indices);

    std::vector<Detection> detections;
    for (int idx : indices)
        detections.push_back({boxes[idx], scores[idx]});

    return detections;
}

std::vector<Detection> YoloDetector::detect(const cv::Mat& frame) {
    preprocess(frame);
    context_->executeV2(gpu_buf_);
    return postprocess(frame.cols, frame.rows);
}
