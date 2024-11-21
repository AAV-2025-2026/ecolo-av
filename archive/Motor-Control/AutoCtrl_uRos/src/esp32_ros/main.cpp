
#include <Arduino.h>
#include  "AAV_fns/AAV_fns.h"
#include "./hardware_fns/hardware_config.h"
#include "./uRos_fns/uRos_fns.h"
#include "./SteeringBraking/Braking.h"

// Target setpoint and integral value
int setpoint = 0;
float intval = 0;
int maxPower = 3200;
float real_power = 0;
float power = 0;
float prev_error = 0;
unsigned long lastTime = 0;

// Parameters that can be changed on the fly
int P = 140;
int I = 0.5;
int D = 0;
int integralLimit = 1000;
int positionDeadzone = 1;
int errorLimit = 2048;

bool ros_enabled = true;

Adafruit_MCP4725 dac;
std_msgs__msg__Int32 msg_int32;
std_msgs__msg__Int32 msg_int32_2;
sensor_msgs__msg__Joy msg_joy;
aav_drive_msg__msg__Drive msg_drive;
ackermann_msgs__msg__AckermannDrive msg_ackermann;
//rcl_node_t node;
//uRos_s testSetup_throttle = uRos_s();  // Initialize the object properly if needed.
uRos_s testSetup = uRos_s();  // Initialize the object properly if needed.


TaskHandle_t TaskCore0;//Core 0 used for microROS, and other communication and soft(er) realtime things
TaskHandle_t TaskCore2;//Core 0 used for microROS, and other communication and soft(er) realtime things
TaskHandle_t TaskCore1;//Core 1 used for signals, PID loops, Sensor reading, motor control. hard(er) realtime



void setup() {
 Serial.begin(115200);
  // xTaskCreatePinnedToCore(
  //     microROS_Task,          // Task function
  //     "Task0",        // Name of task
  //     4096,           // Stack size in words
  //     NULL,           // Task input parameter
  //     1,              // Priority of the task
  //     &TaskCore0,     // Task handle
  //     0);             // Core 0
  //motor_controller_setup();
  hardware_setup();

  xTaskCreatePinnedToCore(
      microROS_Task,          // Task function
      "Task1",        // Name of task
      8192,           // Stack size in words
      NULL,           // Task input parameter
      2,              // Priority of the task
      &TaskCore2,     // Task handle
      0);  

    xTaskCreatePinnedToCore(
     brakingPID_task,          // Task function
    "Task2",        // Name of task
    4096,           // Stack size in words
    NULL,           // Task input parameter
    2,              // Priority of the task
    &TaskCore1,     // Task handle
    0); 
  
  


  //I know I am not supposed to commit passwords but it is behind a vpn
  //set_microros_wifi_transports("BELL310", "376F57AF1739", "192.168.2.58", 8888);
  // uRos_init_wireless_node_int32_2(&testSetup, &braking_callback, &throttle_callback, &msg_int32, &msg_int32_2,
  //                           "AAVwifi", "aav@2023", "192.168.1.126", 8888, "micro_ros_arduino_wifi_node_car", "/brake");


//   uRos_init_wireless_node_drive(&testSetup, &throttle_callback_Drive, &msg_drive,
//                             "AAVwifi", "aav@2023", "192.168.1.126", 8887, "micro_ros_arduino_wifi_node_car", "/driveData");

 uRos_init_wireless_node_ackermann(&testSetup, &throttle_callback_ackermann, &msg_ackermann,
                            "AAVwifi", "aav@2023", "192.168.1.126", 8887, "micro_ros_arduino_wifi_node_car", "/driveData");

//   // uRos_init_wireless_node_int32(&testSetup, &throttle_callback, &msg_int32, "BELL310", "376F57AF1739", "192.168.2.58", 8888, "micro_ros_arduino_wifi_node_car", "/brake" );
  // Serial.print("init");





  
  
}

void loop() {

  //rclc_executor_spin_some(&(testSetup.executor), RCL_MS_TO_NS(800));
}

