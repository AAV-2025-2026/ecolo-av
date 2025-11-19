cmake_minimum_required(VERSION 3.8)
project(camera_decode)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(std_msgs REQUIRED)
find_package(OpenCV REQUIRED)
find_package(PkgConfig REQUIRED)

pkg_check_modules(LIBAV REQUIRED IMPORTED_TARGET
    libavcodec
    libavformat
    libavutil
    libswscale
)

# Find NVIDIA Multimedia API
find_path(NVMM_INCLUDE_DIR
  NAMES NvVideoDecoder.h
  PATHS /usr/src/jetson_multimedia_api/include
)

find_library(NVBUF_UTILS_LIB
  NAMES nvbuf_utils
  PATHS /usr/lib/aarch64-linux-gnu/tegra
)

find_library(NVBUFSURFACE_LIB
  NAMES nvbufsurface
  PATHS /usr/lib/aarch64-linux-gnu/tegra
)

find_library(NVBUFSURFTRANSFORM_LIB
  NAMES nvbufsurftransform
  PATHS /usr/lib/aarch64-linux-gnu/tegra
)

# Include directories
include_directories(
  include
  ${NVMM_INCLUDE_DIR}
)

# Create library
add_library(${PROJECT_NAME}_lib
  src/nvdec_decoder.cpp
  src/rtsp_handler.cpp
)

target_link_libraries(${PROJECT_NAME}_lib
  PkgConfig::LIBAV
  ${NVBUF_UTILS_LIB}
  ${NVBUFSURFACE_LIB}
  ${NVBUFSURFTRANSFORM_LIB}
)

ament_target_dependencies(${PROJECT_NAME}_lib
  rclcpp
  sensor_msgs
  cv_bridge
  OpenCV
)

# Create executable
add_executable(camera_decode_node src/camera_decode_node.cpp)

target_link_libraries(camera_decode_node
  ${PROJECT_NAME}_lib
)

ament_target_dependencies(camera_decode_node
  rclcpp
  sensor_msgs
  cv_bridge
  image_transport
  std_msgs
  OpenCV
)

# Install targets
install(TARGETS
  camera_decode_node
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
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
