cmake_minimum_required(VERSION 3.10)
# A Rust package, built like aav_imu_yahboom: CMake only runs cargo and installs the
# result, so colcon, `ros2 run aav_hud_raylib hud` and launch files treat it like any node.
project(aav_hud_raylib NONE)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})

# raylib draws through GLFW, which needs X11 and OpenGL's headers on Linux. A machine
# without them (a headless server, CI) still builds the rest of the workspace: the HUD is
# skipped there, with a warning that says what to install.
if(UNIX AND NOT APPLE)
  # FindX11 test-compiles its checks, so it needs C (the project itself is NONE).
  enable_language(C)
  find_package(X11)
  find_package(OpenGL)
  if(NOT (X11_FOUND AND X11_Xrandr_FOUND AND X11_Xinerama_FOUND AND X11_Xcursor_FOUND
          AND X11_Xi_FOUND AND OPENGL_FOUND))
    message(WARNING "aav_hud_raylib: no X11/OpenGL headers here, so the HUD isn't built. "
      "On Ubuntu: sudo apt install libx11-dev libxrandr-dev libxinerama-dev "
      "libxcursor-dev libxi-dev libgl-dev")
    ament_package()
    return()
  endif()
endif()

find_program(CARGO cargo)
if(NOT CARGO)
  message(FATAL_ERROR "cargo not found: build with `pixi run build`, or install Rust 1.88 "
    "or newer with rustup (Ubuntu's apt cargo is too old for rclrs and raylib)")
endif()

# Build in colcon's build folder, not in src/. cargo itself decides what's out of date.
# make's jobserver flags are dropped: cargo can't reach the jobserver from here, and says so.
set(CARGO_TARGET_DIR ${CMAKE_CURRENT_BINARY_DIR}/target)
add_custom_target(cargo_build ALL
  COMMAND ${CMAKE_COMMAND} -E env --unset=MAKEFLAGS --unset=MFLAGS --unset=CARGO_MAKEFLAGS
    CARGO_TARGET_DIR=${CARGO_TARGET_DIR}
    ${CARGO} build --release --locked --quiet --bin hud
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  COMMENT "cargo build --release --bin hud (raylib from source the first time: a minute)"
  VERBATIM)

install(PROGRAMS ${CARGO_TARGET_DIR}/release/hud
  DESTINATION lib/${PROJECT_NAME})

ament_package()
