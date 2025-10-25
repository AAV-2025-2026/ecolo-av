cmake_minimum_required(VERSION 4.1.1)
project(BodyControlModule)

file(GLOB_RECURSE SRC_CODE
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.hpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.h"
)

add_executable(BodyControlModule ${SRC_CODE})
