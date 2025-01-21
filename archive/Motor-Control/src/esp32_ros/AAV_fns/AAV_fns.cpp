
#include "AAV_fns.h"
#include "../hardware_fns/hardware_fns.h"

extern Adafruit_MCP4725 dac;
extern bool ackermann_recv;

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

    USER_SERIAL.print("voltage level: ");
    USER_SERIAL.println( (int) msg_mag);
    dac.setVoltage(msg_mag, false);

  }

}


void throttle_callback_Drive(const void * msgin){
  const aav_drive_msg__msg__Drive * msg = (const aav_drive_msg__msg__Drive *)msgin;
  uint16_t msg_mag;

  

  if (msg != NULL) {
    
    ackermann_recv = true;

    if(msg->dir){
      digitalWrite(DIR_PIN, HIGH);
      digitalWrite(LED_PIN, HIGH);
    }else{
      digitalWrite(DIR_PIN, LOW);
      digitalWrite(LED_PIN, LOW);
    }
      
     

    USER_SERIAL.print("voltage level(drv): ");
    USER_SERIAL.print( (int) msg->throttle);
    USER_SERIAL.print("  dir: "); USER_SERIAL.println((int) msg->dir);
    dac.setVoltage((uint16_t)msg->throttle, false);
    
  }

}


void throttle_callback_ackermann(const void * msgin){
  const ackermann_msgs__msg__AckermannDrive * msg = (const ackermann_msgs__msg__AckermannDrive *)msgin;

  USER_SERIAL.println("recv");
  USER_SERIAL.print(readSwitch(USE_RC, false));
  digitalWrite(2, HIGH);
  if (msg != NULL || readSwitch(USE_RC, false)) {
    
    
    uint16_t accelMag;
    bool dir;
   
    
    
    if(!readSwitch(USE_RC, false)){

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
      setpoint = map((long) msg->steering_angle,-3200, 3200, 0, 100);
    }else{
      setpoint = map((long) readChannel(STR_RC, -255, 255, 0),-3200, 3200, 0, 100);
      accelMag = readChannel(THR_RC, -2000, 2000, 0);
      USER_SERIAL.println("USING RC");
    }
    
    USER_SERIAL.print("Steering Angle: "); USER_SERIAL.print((int) accelMag);
    USER_SERIAL.print("   voltage level(drv): ");
    USER_SERIAL.print( (int) accelMag);
    USER_SERIAL.print("  dir: "); USER_SERIAL.println((int) dir);
    dac.setVoltage((uint16_t) accelMag, false);

    digitalWrite(2,LOW);
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

    USER_SERIAL.print("voltage level: ");
    USER_SERIAL.println( (int) msg_mag);
    dac.setVoltage(msg_mag, false);
    
  }

}
void setPosition(int set){
  setpoint = set;
}

void braking_callback(const void *msgin){
  const std_msgs__msg__Int32 * msg = (const std_msgs__msg__Int32 *)msgin;
  USER_SERIAL.println(msg->data);
  USER_SERIAL.println("recv");
  if(msg != NULL){
  setPosition(msg->data);
  //USER_SERIAL.print("Recevied position: ");
  //USER_SERIAL.println(msg->data);
  }
}




