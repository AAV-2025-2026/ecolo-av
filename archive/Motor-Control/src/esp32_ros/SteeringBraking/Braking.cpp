#include "Braking.h"


extern PID_vals steer_vals;
extern PID_vals brake_vals;

int readByte()
{
  char c;
  CTRL_SERIAL.setTimeout(10);//set timeout for debugging if nothing is recieved
  if(CTRL_SERIAL.readBytes(&c, 1) == 0)
  {
    return -1;  // Return -1 if no byte received
  }
  return (byte)c;  // Return the byte read
}

// Function to exit safe mode and enable motor movement
// This must be called when the controller restarts or after any error
void exitSafeStart()
{
  CTRL_SERIAL.write(0x83);  // Command to exit safe start
}

// Function to set motor speed
// Speed should be in the range -3200 to 3200
void setMotorSpeed(int speed)
{
  USER_SERIAL.println("setMotorSpeed");
  // Handle negative speed (reverse)
  if (speed < 0)
  {
    CTRL_SERIAL.write(0x86);  // Motor reverse command
    speed = -speed;       // Convert speed to positive
  }
  else
  {
    CTRL_SERIAL.write(0x85);  // Motor forward command
  }

  // Send the speed (two bytes, split between 5 and 7 bits)
  CTRL_SERIAL.write(speed & 0x1F);      // Send the least significant 5 bits
  CTRL_SERIAL.write((speed >> 5) & 0x7F);  // Send the most significant 7 bits
}

// Function to get a scaled sensor value from command A1
float getA1_scaled()
{
  CTRL_SERIAL.write(0xA1);  // Command A1
  CTRL_SERIAL.write(14);    // Send the scaling factor
  return ((float)(readByte() + 256 * readByte())) / 32.0;  // Scale and return
}

void motor_controller_setup(){
  //  Initialize Serial2 with a baud rate of 9600 bps
  
  CTRL_SERIAL.begin(9600, SERIAL_8N1, RX_PIN, TX_PIN);

  // Initialize regular USER_SERIAL communication for debugging
 

  // Delay to allow motor controller to initialize (5 ms minimum)
  delay(5);
  
  // Send the baud rate auto-detect byte (0xAA) to the motor controller
  CTRL_SERIAL.write(0xAA);

  // Exit safe start to enable the motor
  exitSafeStart();
}

extern int setpoint;
extern float intval;
extern int maxPower;
extern float real_power;
extern float power;
extern float prev_error;
extern unsigned long lastTime;

extern int P;
extern int I;
extern int D;
extern int integralLimit;
extern int positionDeadzone;
extern int errorLimit;


void brakingPID_task(void* parameter) {
  //USER_SERIAL.println("startBrakeTask");
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xFrequency = 10 / portTICK_PERIOD_MS; // 500 ms interval
  while (true) {
    //USER_SERIAL.println("runBrakeTask");

  float brakePos = getA1_scaled();


  if(brakePos>1000){
    brakePos = 0;
  }
  // Get the time elapsed
  unsigned long currentTime = millis();
  //Calculate the elapsed time
  float elapsedTime = (currentTime - lastTime) / 1000.0;
  lastTime = currentTime;

  float error = setpoint - brakePos;

  if(abs(error) < positionDeadzone){
    error = 0;
  }
  error = constrain(error, -errorLimit, errorLimit);

  // Calculate the integral term (accumulates the error over time)
  if(error != 0){
    intval += error * elapsedTime;
    intval = constrain(intval, -integralLimit, integralLimit);
  } else {
    intval = 0;
  }

  // Calculate the proportional term
  float propval = (error * P);

  // Calculate the integral term
  float ival = (intval * I);

  // Calculate the differential term
  float dval = (((error - prev_error)/elapsedTime) * D);
  prev_error = error;

  // Calculate the motor power based on proportional and integral control
  real_power = propval + ival + dval;
  power = real_power;
  // Constrain the power within the range of the 
  power = constrain(power, -maxPower, maxPower);
  // Set the motor speed based on the calculated power
  setMotorSpeed(power);

  // Output the current sensor value
  //USER_SERIAL.print("Pos:");
  //USER_SERIAL.print(brakePos);
  //Set point
  //USER_SERIAL.print(",Setpoint");
  //USER_SERIAL.print(setpoint);
  // Print the real power value
  //USER_SERIAL.print(",RealPower:");
  //USER_SERIAL.print(real_power);
  // Output the calculated motor power
  //USER_SERIAL.print(",Power:");
  //USER_SERIAL.println(power);
  vTaskDelayUntil(&xLastWakeTime, xFrequency); // Wait until next cycle  
    }
}