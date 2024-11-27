
#include "AAV_fns.h"


extern Adafruit_MCP4725 dac;


extern int setpoint;

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


void throttle_callback_Drive(const void * msgin){
  const aav_drive_msg__msg__Drive * msg = (const aav_drive_msg__msg__Drive *)msgin;
  uint16_t msg_mag;

  

  if (msg != NULL) {
    
    

    if(msg->dir){
      digitalWrite(DIR_PIN, HIGH);
      digitalWrite(LED_PIN, HIGH);
    }else{
      digitalWrite(DIR_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
    }
      
     

    Serial.print("voltage level(drv): ");
    Serial.print( (int) msg->throttle);
    Serial.print("  dir: "); Serial.println((int) msg->dir);
    dac.setVoltage((uint16_t)msg->throttle, false);
    
  }

}


void throttle_callback_ackermann(const void * msgin){
  const ackermann_msgs__msg__AckermannDrive * msg = (const ackermann_msgs__msg__AckermannDrive *)msgin;

  //Serial.println("recv");
  

  if (msg != NULL) {
    
    
    uint16_t accelMag;
    bool dir;
    if(msg->acceleration > 0){
      digitalWrite(DIR_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
      accelMag = (uint16_t) msg->acceleration;
      dir = true;
    }else{
      digitalWrite(DIR_PIN, HIGH);
      digitalWrite(LED_PIN, HIGH);
      accelMag = (uint16_t) msg->acceleration * -1;
      dir = false;
    }
      
     
    setpoint = (int) msg->steering_angle;
    Serial.print("Steering Angle: "); Serial.print((int) msg->steering_angle);
    Serial.print("   voltage level(drv): ");
    Serial.print( (int) accelMag);
    Serial.print("  dir: "); Serial.println((int) dir);
    dac.setVoltage((uint16_t) accelMag, false);
    
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
void setPosition(int set){
  setpoint = set;
}

void braking_callback(const void *msgin){
  const std_msgs__msg__Int32 * msg = (const std_msgs__msg__Int32 *)msgin;
  Serial.println(msg->data);
  Serial.println("recv");
  if(msg != NULL){
  setPosition(msg->data);
  //Serial.print("Recevied position: ");
  //Serial.println(msg->data);
  }
}




