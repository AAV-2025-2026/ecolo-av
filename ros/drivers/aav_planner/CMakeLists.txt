cmake_minimum_required(VERSION 3.10)
# A Rust package, built the way aav_mppi_lag is: CMake only runs cargo and installs the
# result, so colcon, `ros2 run` and launch files treat planner like any other node.
project(aav_planner NONE)

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
    ${CARGO} build --release --locked --quiet --bin planner
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  COMMENT "cargo build --release --bin planner"
  VERBATIM)

install(PROGRAMS ${CARGO_TARGET_DIR}/release/planner
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  # The planner without ROS: the curves, and the hand-made maps. cargo test -p lattice-planner.
  find_package(ament_cmake_test REQUIRED)
  ament_add_test(planner_logic
    COMMAND ${CMAKE_COMMAND} -E env CARGO_TARGET_DIR=${CARGO_TARGET_DIR}
      ${CARGO} test --release --locked --quiet -p lattice-planner
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    TIMEOUT 300
    GENERATE_RESULT_FOR_RETURN_CODE_ZERO)
endif()

ament_package()
