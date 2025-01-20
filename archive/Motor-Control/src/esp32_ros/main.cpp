
#include <Arduino.h>
#include  "AAV_fns/AAV_fns.h"
#include "./hardware_fns/hardware_config.h"
#include "./uRos_fns/uRos_fns.h"
#include "./SteeringBraking/Braking.h"
bool ackermann_recv;
// Target setpoint and integral value
int setpoint = 0;
float intval = 0;
int maxPower = 3200;
float real_power = 0;
float power = 0;
float prev_error = 0;
unsigned long lastTime = 0;


// Parameters that can be changed on the fly for steering
int P = 140;
float I = 0.5;
int D = 0;
int integralLimit = 1000;
int positionDeadzone = 1;
int errorLimit = 2048;

PID_vals steer_vals = PID_vals();
PID_vals brake_vals = PID_vals();

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


    //this should be a constructor or basically anything but this
    steer_vals.setpoint = 0;
    steer_vals.intval = 0;
    steer_vals.maxPower = 3200;
    steer_vals.real_power = 0;
    steer_vals.power = 0;
    steer_vals.prev_error = 0;
    steer_vals.lastTime = 0;
    steer_vals.P = 140;
    steer_vals.I = 0.5;
    steer_vals.D = 0;
    steer_vals.integralLimit = 1000;
    steer_vals.positionDeadzone = 1;
    steer_vals.errorLimit = 2048;

    //this should be a constructor or basically anything but this
    brake_vals.setpoint = 0;
    brake_vals.intval = 0;
    brake_vals.maxPower = 3200;
    brake_vals.real_power = 0;
    brake_vals.power = 0;
    brake_vals.prev_error = 0;
    brake_vals.lastTime = 0;
    brake_vals.P = 140;
    brake_vals.I = 0.5;
    brake_vals.D = 0;
    brake_vals.integralLimit = 1000;
    brake_vals.positionDeadzone = 1;
    brake_vals.errorLimit = 2048;

    motor_controller_setup();
    USER_SERIAL.begin(115200);

    hardware_setup();


#ifdef TRANSPORT_WIFI
    // uRos_init_wireless_node_ackermann(&testSetup, &throttle_callback_ackermann, &msg_ackermann,
    //                                 "BELL310", "376F57AF1739", "192.168.2.58", 8887, "micro_ros_arduino_wifi_node_car", "/driveData");
    uRos_init_wireless_node_ackermann(&testSetup, &throttle_callback_ackermann, &msg_ackermann,
                                      "AAVwifi", "aav@2023", "192.168.1.126", 8888, "micro_ros_arduino_wifi_node_car", "/driveData");
#endif
#ifdef TRANSPORT_SERIAL
    uRos_init_serial_node_ackermann(&testSetup, &throttle_callback_ackermann, &msg_ackermann, "micro_ros_arduino_wifi_node_car", "/driveData");
#endif
    digitalWrite(GREEN_LED_PIN, LOW);
    xTaskCreatePinnedToCore(
      microROS_Task,          // Task function
      "Task1",        // Name of task
      4096,           // Stack size in words
      NULL,           // Task input parameter
      1,              // Priority of the task
      &TaskCore2,     // Task handle
      1);

    xTaskCreatePinnedToCore(
     brakingPID_task,          // Task function
    "Task2",        // Name of task
    4096,           // Stack size in words
    NULL,           // Task input parameter
    1,              // Priority of the task
    &TaskCore1,     // Task handle
    1);
  
  


  //I know I am not supposed to commit passwords but it is behind a vpn
  //set_microros_wifi_transports("BELL310", "376F57AF1739", "192.168.2.58", 8888);
  // uRos_init_wireless_node_int32_2(&testSetup, &braking_callback, &throttle_callback, &msg_int32, &msg_int32_2,
  //                           "AAVwifi", "aav@2023", "192.168.1.126", 8888, "micro_ros_arduino_wifi_node_car", "/brake");


//   uRos_init_wireless_node_drive(&testSetup, &throttle_callback_Drive, &msg_drive,
//                             "AAVwifi", "aav@2023", "192.168.1.126", 8887, "micro_ros_arduino_wifi_node_car", "/driveData");


//   // uRos_init_wireless_node_int32(&testSetup, &throttle_callback, &msg_int32, "BELL310", "376F57AF1739", "192.168.2.58", 8888, "micro_ros_arduino_wifi_node_car", "/brake" );
  // Serial.print("init");





  
  
}

void loop() {

  //rclc_executor_spin_some(&(testSetup.executor), RCL_MS_TO_NS(800));
}

