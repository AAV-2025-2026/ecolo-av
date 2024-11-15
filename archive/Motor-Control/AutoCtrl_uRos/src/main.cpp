
#include <Arduino.h>
#include  "AAV_fns/AAV_fns.h"
#include "./hardware_fns/hardware_config.h"
#include "./uRos_fns/uRos_fns.h"
Adafruit_MCP4725 dac;
std_msgs__msg__Int32 msg_int32;
sensor_msgs__msg__Joy msg_joy;
uRos_s testSetup = uRos_s();  // Initialize the object properly if needed.


TaskHandle_t TaskCore0;//Core 0 used for microROS, and other communication and soft(er) realtime things
TaskHandle_t TaskCore1;//Core 1 used for signals, PID loops, Sensor reading, motor control. hard(er) realtime


void setup() {
 
  // xTaskCreatePinnedToCore(
  //     microROS_Task,          // Task function
  //     "Task0",        // Name of task
  //     4096,           // Stack size in words
  //     NULL,           // Task input parameter
  //     1,              // Priority of the task
  //     &TaskCore0,     // Task handle
  //     0);             // Core 0

  xTaskCreatePinnedToCore(
      microROS_Task_joy,          // Task function
      "Task0",        // Name of task
      4096,           // Stack size in words
      NULL,           // Task input parameter
      1,              // Priority of the task
      &TaskCore0,     // Task handle
      0);             // Core 0
  Serial.begin(115200);
  
  hardware_setup();

  uRos_init_wireless_node_joy(&testSetup, &throttle_callback, &msg_joy, 
                            "AAVwifi", "aav@2023", "192.168.1.126", 8888, "micro_ros_arduino_wifi_node_car", "joy");



  
  
}

void loop() {

  //rclc_executor_spin_some(&(testSetup.executor), RCL_MS_TO_NS(800));
}

