#include <Arduino.h>
#include "../hardware_fns/hardware_config.h"



typedef struct pid_s{
    int setpoint;
    float intval;
    int maxPower;
    float real_power;
    float power;
    float prev_error;
    unsigned long lastTime;
    float P;
    float I;
    float D;
    int integralLimit;
    int positionDeadzone;
    int errorLimit;
}PID_vals;


void brakingPID_task(void* parameter);

void motor_controller_setup();