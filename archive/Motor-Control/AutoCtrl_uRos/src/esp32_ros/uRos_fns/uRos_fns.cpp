

#include "uRos_fns.h"
extern rcl_node_t node;
extern uRos_s testSetup;
extern uRos_s testSetup_throttle;



int uRos_init_wireless_node_int32(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, std_msgs__msg__Int32 *msg, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName){
  rcl_ret_t status;
  //192.168.1.126
  IPAddress local_IP(192, 168, 2, 58);
  set_microros_wifi_transports(ssid, pass, local_IP, (uint16_t) port);
  
  // set_microros_wifi_transports(ssid, pass, ip, (uint16_t) port);
  Serial.println("WIFI");
  Serial.println(WiFi.BSSIDstr());

  delay(2000);

  uRosStruct->allocator = rcl_get_default_allocator();

  // Create init_options
  status = rclc_support_init(&uRosStruct->support, 0, NULL, &uRosStruct->allocator);
  Serial.print("Support_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
    
    
  // Create node
  status = rclc_node_init_default(&node, "micro_ros_arduino_wifi_node_car", "", &uRosStruct->support);
  Serial.print("node_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
    
    
  //Create subscriber
  status = rclc_subscription_init_best_effort(
  &uRosStruct->subscriber_1,
  &uRosStruct->node,
  ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32), topicName);
  Serial.print("subscriber_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  

  // Create executor
  status = rclc_executor_init(&uRosStruct->executor, &uRosStruct->support.context, 1, &uRosStruct->allocator);
  Serial.print("executor_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}

  status = rclc_executor_add_subscription(&uRosStruct->executor, &uRosStruct->subscriber_1, msg, *subscription_callback, ON_NEW_DATA);
  Serial.print("ex add sub init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  
  return status;
}

int uRos_init_wireless_node_drive(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback, aav_drive_msg__msg__Drive *msg, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName){
  rcl_ret_t status;
  //192.168.1.126
  IPAddress local_IP(192, 168, 1, 126);
  set_microros_wifi_transports(ssid, pass, local_IP, (uint16_t) port);
  
  // set_microros_wifi_transports(ssid, pass, ip, (uint16_t) port);
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
  &uRosStruct->subscriber_1,
  &uRosStruct->node,
  ROSIDL_GET_MSG_TYPE_SUPPORT(aav_drive_msg, msg, Drive), topicName);
  Serial.print("subscriber_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  

  // Create executor
  status = rclc_executor_init(&uRosStruct->executor, &uRosStruct->support.context, 1, &uRosStruct->allocator);
  Serial.print("executor_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}

  status = rclc_executor_add_subscription(&uRosStruct->executor, &uRosStruct->subscriber_1, msg, *subscription_callback, ON_NEW_DATA);
  Serial.print("ex add sub init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  
  return status;
}

int uRos_init_wireless_node_int32_2(uRos_s *uRosStruct, rclc_subscription_callback_t subscription_callback_1, 
                                    rclc_subscription_callback_t subscription_callback_2, std_msgs__msg__Int32 *msg_1, std_msgs__msg__Int32 *msg_2, char *ssid, char *pass, char *ip, int port, char *nodeName, char *topicName){
  rcl_ret_t status;
  //192.168.1.126
  IPAddress local_IP(192, 168, 2, 58);
  set_microros_wifi_transports(ssid, pass, local_IP, (uint16_t) port);
  
  // set_microros_wifi_transports(ssid, pass, ip, (uint16_t) port);
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
  &uRosStruct->subscriber_1,
  &uRosStruct->node,
  ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32), topicName);
  Serial.print("subscriber_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}

  status = rclc_subscription_init_best_effort(
  &uRosStruct->subscriber_2,
  &uRosStruct->node,
  ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32), "/throttle_1");
  Serial.print("subscriber_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  

  // Create executor
  status = rclc_executor_init(&uRosStruct->executor, &uRosStruct->support.context, 2, &uRosStruct->allocator);
  Serial.print("executor_init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}


  status = rclc_executor_add_subscription(&uRosStruct->executor, &uRosStruct->subscriber_1, msg_1, *subscription_callback_1, ON_NEW_DATA);
  Serial.print("ex add sub init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}

  status = rclc_executor_add_subscription(&uRosStruct->executor, &uRosStruct->subscriber_2, msg_2, *subscription_callback_2, ON_NEW_DATA);
  Serial.print("ex add sub init status: "); Serial.println(status);
  if(status != RCL_RET_OK){return 0;}
  
  return status;
}




void microROS_Task(void* parameter) {
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xFrequency = 10 / portTICK_PERIOD_MS; // 500 ms interval
  
    
    while (true) {
        //Serial.println("braketask");
        rclc_executor_spin_some(&testSetup.executor, RCL_MS_TO_NS(100));
        vTaskDelayUntil(&xLastWakeTime, xFrequency); // Wait until next cycle  
    }
}



// void microROS_Task_joy(void* parameter) {
//     while (true) {
//         rclc_executor_spin_some(&testSetup.executor, RCL_MS_TO_NS(100));
//         vTaskDelay(100 / portTICK_PERIOD_MS); // Task delay
//     }
// }


