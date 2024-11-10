

#include "uRos_fns.h"

int uRos_init_wireless_node(rcl_node_t node, rcl_allocator_t allocator, rclc_support_t support, char *ssid, char *pass, char *ip, int port, char *nodeName){
    
    rcl_ret_t status;
    status = rclc_support_init(&support, 0, NULL, &allocator);
    if(status != RCL_RET_OK){
        Serial.print("uRos Support Init Error. ");
        Serial.println(status);
        return 0;
    }


    status = rclc_node_init_default(&node, "micro_ros_arduino_wifi_node_car", "", &support);
    if(status != RCL_RET_OK){
        Serial.print("uRos node Init Error. ");
        Serial.println(status);
        return 0;
    }

    return 1;
}




int uRos_create_subscriber_Int32(rcl_subscription_t subscriber, rcl_node_t node, char *topic_name){
    rcl_ret_t status;

    
    rclc_subscription_init_best_effort(
    &subscriber,
    &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
    topic_name);

    if(status != RCL_RET_OK){
        Serial.print("uRos subscriber Init Error. ");
        Serial.println(status);
        return 0;
    }
    return 1;
  
}


int uRos_create_executor(rclc_executor_t *executor, rcl_subscription_t *subscriber, rclc_support_t support, 
                         rcl_allocator_t *allocator, void *msg, rclc_subscription_callback_t subscription_callback){

  rclc_executor_init(executor, &support.context, 1, allocator);
  rclc_executor_add_subscription(executor, subscriber, &msg, subscription_callback, ON_NEW_DATA);

  return 1;
}



