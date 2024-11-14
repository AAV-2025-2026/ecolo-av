

#include "AAV_fns.h"
#include "../uRos_fns/uRos_fns.h"
#include <micro_ros_arduino.h>
#include <stdlib.h>
#include <stdio.h>
#include <rcl/rcl.h>
#include <rmw/rmw.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>



#include <std_msgs/msg/float32_multi_array.h>
#include <std_msgs/msg/int32.h>
#include <sensor_msgs/msg/joy.h>
DacESP32 dac1(DAC_PIN_1);

void throttle_callback(const void * msgin){
    Serial.println("callback");
    const std_msgs__msg__Int32 * msg = (const std_msgs__msg__Int32 *)msgin;
    if (msg != NULL) {
    
    Serial.print("voltage level: ");
    Serial.println( (int) msg->data);
    if((int)msg->data < 0){
      digitalWrite(DIR_PIN, LOW);
    }else{
      digitalWrite(DIR_PIN, HIGH);
    }
    dac1.outputVoltage((uint8_t) abs(msg->data));
    }

}