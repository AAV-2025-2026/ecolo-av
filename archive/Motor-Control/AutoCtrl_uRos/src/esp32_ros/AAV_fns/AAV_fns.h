#include "../hardware_fns/hardware_fns.h"


 #include <micro_ros_platformio.h>
//#include <micro_ros_arduino.h>
#include <stdlib.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rmw/rmw.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>



#include <std_msgs/msg/float32_multi_array.h>
#include <std_msgs/msg/int32.h>
#include <sensor_msgs/msg/joy.h>
#include <aav_drive_msg/msg/drive.h>



void throttle_callback(const void * msgin);

void throttle_callback_joy(const void * msgin);

void braking_callback(const void *msgin);