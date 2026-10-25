

#undef TRANSPORT_SERIAL
#define TRANSPORT_WIFI
#ifndef HARDWARE_CONFIG_H
#define HARDWARE_CONFIG_H


//rc pins
//22,0,34,35

//from motor controllers back: 35, 34, 0, 23: steering, throttle rev_en, RC_EN
#define USE_RC 23
#define REV_EN 0
#define THR_RC 34
#define STR_RC 35


#define DIR_PIN 33
#define LED_PIN 2


#define I2C_SDA 23
#define I2C_SCL 22

#define BLUE_LED_PIN 14
#define RED_LED_PIN 18
#define GREEN_LED_PIN 19

#define ROS_SERIAL Serial1
#define USER_SERIAL Serial
#define CTRL_SERIAL Serial2

#define RX_PIN_1 5
#define TX_PIN_1 4

#define TX_PIN 27
#define RX_PIN 26
#endif