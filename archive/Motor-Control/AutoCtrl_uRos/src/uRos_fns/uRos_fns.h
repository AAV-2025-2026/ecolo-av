
#include <Arduino.h>

#include "../hardware_fns/hardware_config.h"
#include <micro_ros_arduino.h>
#include <stdlib.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rmw/rmw.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/init.h>
#include <rclc/executor.h>




#include <std_msgs/msg/float32_multi_array.h>
#include <std_msgs/msg/int32.h>
#include <sensor_msgs/msg/joy.h>




/*_____________________________________MACROS_____________________________________________________





*/


typedef struct uRos_struct_s{
    rcl_node_t node;
    rcl_allocator_t allocator;
    rclc_support_t support;
    rcl_subscription_t subscriber;
    rclc_executor_t executor;

}uRos_s;


int uRos_init_wireless_node_int32(uRos_s setup, char *ssid, char *pass, char *ip, int port, char *nodeName);
