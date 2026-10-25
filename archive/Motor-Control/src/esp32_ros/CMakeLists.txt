

# Minimum CMake version required
cmake_minimum_required(VERSION 3.15)

# Project name
project(PlatformIO_Arduino_Project)

# Include PlatformIO's CMake integration
set(CMAKE_EXPORT_COMPILE_COMMANDS ON) # Enable CMake Code Analyzer
execute_process(
        COMMAND platformio project init --ide cmake
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
)

# Add source files
file(GLOB_RECURSE SRC_FILES src/*.cpp src/*.c)
file(GLOB_RECURSE HEADER_FILES include/*.h include/*.hpp)

# Include PlatformIO's configuration for the target environment
include_directories(${CMAKE_SOURCE_DIR}/include)

# Add executable for CMake analysis
add_executable(${PROJECT_NAME} ${SRC_FILES} ${HEADER_FILES})

# Link PlatformIO environment
set(PLATFORMIO_ENV "YOUR_PLATFORMIO_ENVIRONMENT") # Replace with your environment
set(PLATFORMIO_BUILD_DIR "${CMAKE_SOURCE_DIR}/.pio/build/${PLATFORMIO_ENV}")

target_include_directories(${PROJECT_NAME} PRIVATE ${PLATFORMIO_BUILD_DIR})

# Link against PlatformIO libraries
target_link_libraries(${PROJECT_NAME} PRIVATE ${PLATFORMIO_BUILD_DIR}/libPlatformIO.a)

# Note: Replace "YOUR_PLATFORMIO_ENVIRONMENT" with the name of the target environment
# (e.g., `uno`, `esp32dev`, etc.) as defined in your platformio.ini file.
