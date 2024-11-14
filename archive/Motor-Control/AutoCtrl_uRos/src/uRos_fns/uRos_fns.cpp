

#include "uRos_fns.h"

int uRos_init_wireless_node_int32(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, std_msgs__msg__Int32 *msg, char *ssid, char *pass, char *ip, int port, char *nodeName){
  rcl_ret_t status;
  set_microros_wifi_transports(ssid, pass, ip, (uint) port);
  Serial.println("WIFI");
  Serial.println(WiFi.BSSIDstr());

  delay(2000);

  uRosStruct->allocator = rcl_get_default_allocator();

  // Create init_options
  status = rclc_support_init(&uRosStruct->support, 0, NULL, &uRosStruct->allocator);
  Serial.print("Support_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
    
    
  // Create node
  status = rclc_node_init_default(&uRosStruct->node, "micro_ros_arduino_wifi_node_car", "", &uRosStruct->support);
  Serial.print("node_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
    
    
  //Create subscriber
  status = rclc_subscription_init_best_effort(
  &uRosStruct->subscriber,
  &uRosStruct->node,
  ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
  "/throttle");
  Serial.print("subscriber_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  

  // Create executor
  status = rclc_executor_init(&uRosStruct->executor, &uRosStruct->support.context, 1, &uRosStruct->allocator);
  Serial.print("executor_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}

  status = rclc_executor_add_subscription(&uRosStruct->executor, &uRosStruct->subscriber, msg, *subscription_callback, ON_NEW_DATA);
  Serial.print("ex add sub init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  
  return status;
}




