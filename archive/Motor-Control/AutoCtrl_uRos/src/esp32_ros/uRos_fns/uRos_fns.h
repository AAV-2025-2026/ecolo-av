
#include <Arduino.h>

#include "../hardware_fns/hardware_config.h"
#include <micro_ros_platformio.h>
//#include <micro_ros_arduino.h>
#include <stdlib.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rmw/rmw.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/init.h>
#include <rclc/executor.h>
#include <platform_code/micro_ros_platformio.h>




#include <std_msgs/msg/float32_multi_array.h>
#include <std_msgs/msg/int32.h>
#include <sensor_msgs/msg/joy.h>
#include <aav_drive_msg/msg/drive.h>





/*_____________________________________MACROS_____________________________________________________





*/


typedef struct uRos_struct_s{
    rcl_node_t node;
    rcl_allocator_t allocator;
    rclc_support_t support;
    rcl_subscription_t subscriber_1;
    rcl_subscription_t subscriber_2;
    rclc_executor_t executor;
    rclc_executor_t executor_2;

}uRos_s;

int uRos_init_wireless_node_drive(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, aav_drive_msg__msg__Drive *msg, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName);
int uRos_init_wireless_node_int32(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, std_msgs__msg__Int32 *msg, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName);
int uRos_init_wireless_node_joy(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, sensor_msgs__msg__Joy *msg, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName);
int uRos_init_wireless_node_int32_2(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback_1, 
                                    rclc_subscription_callback_t subscription_callback_2, std_msgs__msg__Int32 *msg_1, std_msgs__msg__Int32 *msg_2, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName);

void microROS_Task(void* parameter);
void microROS_Task_joy(void* parameter);
void microROS_Task_throttle(void* parameter);