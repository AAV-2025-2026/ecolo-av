cmake_minimum_required(VERSION 3.8)
project(camera_decode)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(std_msgs REQUIRED)
find_package(vision_msgs REQUIRED)
find_package(OpenCV REQUIRED)
find_package(PkgConfig REQUIRED)
find_package(CUDA REQUIRED)                         

pkg_check_modules(LIBAV REQUIRED IMPORTED_TARGET
    libavcodec
    libavformat
    libavutil
    libswscale
)

# NVIDIA Multimedia API 
find_path(NVMM_INCLUDE_DIR
  NAMES NvVideoDecoder.h
  PATHS /usr/src/jetson_multimedia_api/include
)

find_library(NVBUFSURFACE_LIB
  NAMES nvbufsurface
  PATHS
    /usr/lib/aarch64-linux-gnu/tegra
    /usr/lib/aarch64-linux-gnu/nvidia
    /usr/lib/aarch64-linux-gnu
)

find_library(NVBUFSURFTRANSFORM_LIB
  NAMES nvbufsurftransform
  PATHS
    /usr/lib/aarch64-linux-gnu/tegra
    /usr/lib/aarch64-linux-gnu/nvidia
    /usr/lib/aarch64-linux-gnu
)

# TensorRT paths
find_path(TRT_INCLUDE_DIR
  NAMES NvInfer.h
  PATHS
    /usr/include/aarch64-linux-gnu
    /usr/local/cuda/include
)

find_library(TRT_LIB       NAMES nvinfer       PATHS /usr/lib/aarch64-linux-gnu)
find_library(TRT_PLUGIN_LIB NAMES nvinfer_plugin PATHS /usr/lib/aarch64-linux-gnu)

# Include directories
include_directories(
  include
  ${NVMM_INCLUDE_DIR}
  ${TRT_INCLUDE_DIR}                           
  ${CUDA_INCLUDE_DIRS}                               
)

# Shared lib (nvdec_decoder + yolo_detector)
add_library(${PROJECT_NAME}_lib
  src/nvdec_decoder.cpp
  src/yolo_detector.cpp                              
)

target_link_libraries(${PROJECT_NAME}_lib
  PkgConfig::LIBAV
  ${NVBUFSURFACE_LIB}
  ${NVBUFSURFTRANSFORM_LIB}
  ${TRT_LIB}                                         
  ${TRT_PLUGIN_LIB}                                  
  ${CUDA_LIBRARIES}                                  
  /usr/local/cuda-12.6/targets/aarch64-linux/lib/libcudart.so                                      
)

ament_target_dependencies(${PROJECT_NAME}_lib
  rclcpp
  sensor_msgs
  cv_bridge
  OpenCV
)

# camera_decoder_node 
add_executable(camera_decoder_node src/camera_decoder_node.cpp)

target_link_libraries(camera_decoder_node
  ${PROJECT_NAME}_lib
)

ament_target_dependencies(camera_decoder_node
  rclcpp
  sensor_msgs
  cv_bridge
  image_transport
  std_msgs
  OpenCV
  vision_msgs
)

# stop_sign_node
add_executable(stop_sign_node src/stop_sign_node.cpp)   

target_link_libraries(stop_sign_node
  ${PROJECT_NAME}_lib
)

ament_target_dependencies(stop_sign_node
  rclcpp
  std_msgs
  vision_msgs
  OpenCV
)

# Install
install(TARGETS
  camera_decoder_node
  stop_sign_node                                     
  DESTINATION lib/${PROJECT_NAME}
)

install(TARGETS
  ${PROJECT_NAME}_lib
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(DIRECTORY
  include/
  DESTINATION include
)

install(DIRECTORY
  launch
  config
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
