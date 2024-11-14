
#include <Arduino.h>
#include  "AAV_fns/AAV_fns.h"
#include "./hardware_fns/hardware_config.h"
#include "./uRos_fns/uRos_fns.h"

std_msgs__msg__Int32 msg;
uRos_s testSetup = uRos_s();  // Initialize the object properly if needed.

rclc_support_t *support;
rcl_subscription_t subscriber;
rcl_allocator_t *allocator;
rcl_node_t *node;
rclc_executor_t *executor;


void setup() {
  support = (rclc_support_t *) malloc(sizeof(void *));
  allocator = (rcl_allocator_t *) malloc(sizeof(void *));
  node = (rcl_node_t *) malloc(sizeof(void *));
  
  Serial.begin(115200);
  


  uRos_init_wireless_node(*node, allocator, support, 
                            "AAVwifi", "aav@2023", "192.168.1.126", 8888, "micro_ros_arduino_wifi_node_car");

  

  uRos_create_subscriber_Int32(subscriber, *node, "/throttle");

  Serial.println("here3");
  uRos_create_executor(*executor, subscriber, *support, 
                         *allocator, &msg, throttle_callback);

  Serial.println("here4");
}

void loop() {
  rclc_executor_spin_some(testSetup.executor, RCL_MS_TO_NS(800));
}

