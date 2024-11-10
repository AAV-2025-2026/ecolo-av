#include <Arduino.h>
#include <micro_ros_arduino.h>

#include <stdio.h>
#include <rcl/rcl.h>
#include <rmw/rmw.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>


#include <std_msgs/msg/float32_multi_array.h>
#include <std_msgs/msg/int32.h>
#include <sensor_msgs/msg/joy.h>




/*_____________________________________MACROS_____________________________________________________





*/
int uRos_init_wireless_node(rcl_node_t node, rcl_allocator_t allocator, rclc_support_t support, 
                            char *ssid, char *pass, char *ip, int port, char *nodeName);

int uRos_create_subscriber_Int32(rcl_subscription_t subscriber, rcl_node_t node, char *topic_name);

int uRos_create_executor(rclc_executor_t *executor, rcl_subscription_t *subscriber, rclc_support_t support, 
                         rcl_allocator_t *allocator, void *msg, rclc_subscription_callback_t subscription_callback);

