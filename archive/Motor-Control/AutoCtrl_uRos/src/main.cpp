
#include <Arduino.h>
#include  "AAV_fns/AAV_fns.h"
#include "./hardware_fns/hardware_config.h"
#include "./uRos_fns/uRos_fns.h"

std_msgs__msg__Int32 msg;
uRos_s testSetup = uRos_s();  // Initialize the object properly if needed.

void setup() {
 


  Serial.begin(115200);
  


  uRos_init_wireless_node_int32(&testSetup, &throttle_callback, &msg, 
                            "AAVwifi", "aav@2023", "192.168.1.126", 8888, "micro_ros_arduino_wifi_node_car");



  
  
}

void loop() {

rclc_executor_spin_some(&(testSetup.executor), RCL_MS_TO_NS(800));
}

