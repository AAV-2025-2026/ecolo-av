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

    if((int)msg->throttle < 0){
      msg_mag = (uint16_t) (msg->throttle * -1);

    }else{
      msg_mag = (uint16_t) msg->throttle;

    }

    USER_SERIAL.print("Steering Angle: "); USER_SERIAL.print((int) msg->throttle);
    USER_SERIAL.print("   voltage level(drv): ");
    USER_SERIAL.print( (int) msg->throttle);
    USER_SERIAL.print("  dir: "); USER_SERIAL.println((int) msg->dir);
    dac.setVoltage((uint16_t)msg->throttle, false);
    
  }

}


// =======================  Ackermann + Brake Override  =======================
void throttle_callback_ackermann(const void * msgin){
  const ackermann_msgs__msg__AckermannDrive * msg =
      (const ackermann_msgs__msg__AckermannDrive *) msgin;

  USER_SERIAL.println("recv");
  USER_SERIAL.print(readSwitch(USE_RC, false));
  digitalWrite(LED_PIN, HIGH);

  // If RC switch is OFF, use the Ackermann message (ROS2 control).
  // If RC switch is ON, fall back to RC channels.
  if (msg != NULL || readSwitch(USE_RC, false)) {

    uint16_t accelMag = 0;
    bool dir = true;

    if (!readSwitch(USE_RC, false)) {
      // ---------------- ROS2 control path ----------------
      // Convention:
      //   - msg->acceleration : throttle command in DAC counts (can be negative for reverse)
      //   - msg->steering_angle : brake command [0..BRAKE_SETPOINT_MAX]
      const float BRAKE_CMD_DEADZONE = 1.0f;
      const int   BRAKE_SETPOINT_MAX = 100;

      float throttle_cmd = msg->acceleration;
      float brake_cmd    = msg->steering_angle;

      bool brake_active = (fabs(brake_cmd) > BRAKE_CMD_DEADZONE);

      if (brake_active) {
        // ----- BRAKE OVERRIDE -----
        // Force throttle to zero whenever a non-zero brake command is present.
        accelMag = 0;

        // Map brake command directly into the internal setpoint used by the PID
        if (brake_cmd < 0.0f) {
          brake_cmd = -brake_cmd;
        }
        int sp = (int) constrain(brake_cmd, 0.0f, (float) BRAKE_SETPOINT_MAX);
        setpoint = sp;

      } else {
        // ----- No brake requested: release brake and allow throttle -----
        setpoint = 0;

        if (throttle_cmd > 0.0f) {
          digitalWrite(DIR_PIN, LOW);
          digitalWrite(LED_PIN, LOW);
          accelMag = (uint16_t) throttle_cmd;
          dir = true;
        } else if (throttle_cmd < 0.0f) {
          digitalWrite(DIR_PIN, HIGH);
          digitalWrite(LED_PIN, HIGH);
          accelMag = (uint16_t) (-throttle_cmd);
          dir = false;
        } else {
          accelMag = 0;
        }
      }

    } else {
      // ---------------- RC fallback path ----------------
      setpoint = map((long) readChannel(STR_RC, -255, 255, 0),
                     -3200, 3200, 0, 100);
      accelMag = readChannel(THR_RC, -2000, 2000, 0);
      USER_SERIAL.println("USING RC");
    }

    USER_SERIAL.print("Steering/Brake setpoint: ");
    USER_SERIAL.print((int) setpoint);
    USER_SERIAL.print("   throttle DAC: ");
    USER_SERIAL.print((int) accelMag);
    USER_SERIAL.print("   dir: ");
    USER_SERIAL.println((int) dir);

    dac.setVoltage((uint16_t) accelMag, false);
    digitalWrite(LED_PIN, LOW);
  }
}
// ===========================================================================


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
