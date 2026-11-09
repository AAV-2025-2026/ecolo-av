cmake_minimum_required(VERSION 3.10)
# A Rust package, built the way aav_mppi_lag is: CMake only runs cargo and installs the
# result, so colcon, `ros2 run` and launch files treat navigator like any other node.
project(aav_navigator NONE)

find_package(ament_cmake REQUIRED)

find_program(CARGO cargo)
if(NOT CARGO)
  message(FATAL_ERROR "cargo not found: build with `pixi run build`, or install Rust 1.85 "
    "or newer with rustup (Ubuntu's apt cargo is too old for rclrs)")
endif()

# Build in colcon's build folder, not in src/. cargo itself decides what's out of date.
set(CARGO_TARGET_DIR ${CMAKE_CURRENT_BINARY_DIR}/target)
add_custom_target(cargo_build ALL
  COMMAND ${CMAKE_COMMAND} -E env --unset=MAKEFLAGS --unset=MFLAGS --unset=CARGO_MAKEFLAGS
    CARGO_TARGET_DIR=${CARGO_TARGET_DIR}
    ${CARGO} build --release --locked --quiet --bin navigator
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  COMMENT "cargo build --release --bin navigator"
  VERBATIM)

install(PROGRAMS ${CARGO_TARGET_DIR}/release/navigator
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  # The navigator without ROS: the state machine against a pretend planner and follower.
  find_package(ament_cmake_test REQUIRED)
  ament_add_test(navigator_logic
    COMMAND ${CMAKE_COMMAND} -E env CARGO_TARGET_DIR=${CARGO_TARGET_DIR}
      ${CARGO} test --release --locked --quiet -p navigator
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    TIMEOUT 600
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO)
endif()

ament_package()
