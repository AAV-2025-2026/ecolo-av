
#include "AAV_fns.h"


extern Adafruit_MCP4725 dac;



void throttle_callback(const void * msgin){
  const std_msgs__msg__Int32 * msg = (const std_msgs__msg__Int32 *)msgin;
  uint16_t msg_mag;
  if (msg != NULL) {
    
    
    if((int)msg->data < 0){
      digitalWrite(DIR_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
      msg_mag = (uint16_t) (msg->data * -1);

    }else{
      msg_mag = (uint16_t) msg->data;
      digitalWrite(DIR_PIN, HIGH);
      digitalWrite(LED_PIN, HIGH);

    }

    Serial.print("voltage level: ");
    Serial.println( (int) msg_mag);
    dac.setVoltage(msg_mag, false);
    
  }

}


void throttle_callback_joy(const void * msgin){
  const sensor_msgs__msg__Joy * msg = (const sensor_msgs__msg__Joy *)msgin;
  uint16_t msg_mag;
  if (msg != NULL) {
    
    
    if((int)msg->axes.data[0] < 0){
      digitalWrite(DIR_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
      msg_mag = (uint16_t) (msg->axes.data[0] * -1);

    }else{
      msg_mag = (uint16_t) msg->axes.data[0];
      digitalWrite(DIR_PIN, HIGH);
      digitalWrite(LED_PIN, HIGH);

    }

    Serial.print("voltage level: ");
    Serial.println( (int) msg_mag);
    dac.setVoltage(msg_mag, false);
    
  }

}




