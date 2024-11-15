
#include "AAV_fns.h"


extern Adafruit_MCP4725 dac;



void throttle_callback(const void * msgin){
  const std_msgs__msg__Int32 * msg = (const std_msgs__msg__Int32 *)msgin;
  uint16_t msg_mag;
  if (msg != NULL) {
    
    
    if((int)msg->data < 0){
      digitalWrite(DIR_PIN, LOW);
      msg_mag = (uint16_t) (msg->data * -1);

    }else{
      msg_mag = (uint16_t) msg->data;
      digitalWrite(DIR_PIN, HIGH);

    }

    Serial.print("voltage level: ");
    Serial.println( (int) msg_mag);
    dac.setVoltage(msg_mag, false);
    
  }

}




