

#include "uRos_fns.h"

int uRos_init_wireless_node_int32(uRos_s uRosStruct, rclc_subscription_callback_t subscription_callback, std_msgs__msg__Int32 msg, char *ssid, char *pass, char *ip, int port, char *nodeName){

    set_microros_wifi_transports("BELL310", "376F57AF1739", "192.168.2.58", 8888);
    Serial.println("WIFI");
    Serial.println(WiFi.BSSIDstr());

    delay(2000);

    uRosStruct.allocator = rcl_get_default_allocator();

    // Create init_options
    rclc_support_init(&uRosStruct.support, 0, NULL, &uRosStruct.allocator);

    // Create node
    rclc_node_init_default(&uRosStruct.node, "micro_ros_arduino_wifi_node_car", "", &uRosStruct.support);

    //Create subscriber
    rclc_subscription_init_best_effort(
    &uRosStruct.subscriber,
    &uRosStruct.node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
    "/throttle");
  
  

  // Create executor
  rclc_executor_init(&uRosStruct.executor, &uRosStruct.support.context, 1, &uRosStruct.allocator);
  rclc_executor_add_subscription(&uRosStruct.executor, &uRosStruct.subscriber, &msg, subscription_callback, ON_NEW_DATA);

}




