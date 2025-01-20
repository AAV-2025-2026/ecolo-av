 #include <micro_ros_platformio.h>
#include <Adafruit_BusIO_Register.h>
//#include <micro_ros_arduino.h>
#include <stdlib.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rmw/rmw.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <std_msgs/msg/int32.h>
#include <SPI.h>
#include <Arduino.h>
#include <aav_drive_msg/msg/Drive.h>


#define X_INPUT 36
#define Y_INPUT 39

rcl_publisher_t publisher;
//std_msgs__msg__Int32 msg;
aav_drive_msg__msg__Drive msg;
rclc_support_t support;
rcl_allocator_t allocator;
rcl_node_t node;

#define LED_PIN 13

#define RCCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){error_loop();}}
#define RCSOFTCHECK(fn) { rcl_ret_t temp_rc = fn; if((temp_rc != RCL_RET_OK)){}}


void error_loop(){
  while(1){
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    delay(100);
  }
}

void timer_callback(rcl_timer_t * timer, int64_t last_call_time)
{
  RCLC_UNUSED(last_call_time);
  if (timer != NULL) {
    RCSOFTCHECK(rcl_publish(&publisher, &msg, NULL));
    
  }
}

void setup() {
  IPAddress local_IP(192, 168, 1, 126);
  set_microros_wifi_transports("AAVwifi", "aav@2023", local_IP, (uint16_t) 8887);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  delay(2000);
    Serial.begin(115200);

  pinMode(X_INPUT, INPUT);
  pinMode(Y_INPUT, INPUT);
  allocator = rcl_get_default_allocator();

  //create init_options
  RCCHECK(rclc_support_init(&support, 0, NULL, &allocator));

  // create node
  RCCHECK(rclc_node_init_default(&node, "micro_ros_arduino_wifi_node", "", &support));

  // create publisher
  RCCHECK(rclc_publisher_init_best_effort(
    &publisher,
    &node,
    ROSIDL_GET_MSG_TYPE_SUPPORT(aav_drive_msg, msg, Drive),
    "driveData"));

  
}

void loop() {
    RCSOFTCHECK(rcl_publish(&publisher, &msg, NULL));
    double val = analogRead(X_INPUT);
    
    
    if(val < 1700){
      msg.dir = 0;
      msg.throttle = (uint16_t) (val-1700)*-1;
    }else{
      msg.dir = 1;
      msg.throttle = (uint16_t) (val-1700);
    }
    msg.steering = (uint16_t) analogRead(Y_INPUT);
    Serial.print("throttle: "); Serial.print((int) msg.throttle);Serial.print("  dir: "); Serial.println((int)msg.dir);
    delay(10);
}
