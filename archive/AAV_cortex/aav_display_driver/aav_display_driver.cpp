#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/spi.h"
#include "hardware/i2c.h"
#include "hardware/uart.h"
#include "hardware/pwm.h"
#include "hardware/irq.h"

// ======= SPI Pins ======
#define SPI_PORT spi1   //Spi port 1
#define SPI_CLK_PIN 14  // SPI clock pin - pin 14
#define SPI_MOSI_PIN 15 // SPI MOSI pin - pin 16
#define SPI_CS_PIN 13   // SPI chip select pin - pin 13


// ======= I2C Pins ======
#define I2C_PORT i2c0   // I2C0 pins
#define I2C_SDA_PIN 0   // SDA pin - pin 1
#define I2C_SCL_PIN 1   // SCL pin - pin 2

// ======= LCD Pins ======
#define LCD_RS_PIN 5    // Register Select pin - pin 7
#define LCD_E_PIN 6     // Enable pin - pin 9
#define LCD_D4_PIN 9    // D4 pin - pin 12
#define LCD_D5_PIN 10   // D5 pin - pin 14
#define LCD_D6_PIN 11   // D6 pin - pin 15
#define LCD_D7_PIN 12   // D7 pin - pin 16

#define LCD_BACKLIGHT_PIN 15 // Backlight control pin - pin 18 (PWM_V0)

// ====== 2510SR-1 ======
#define LED_0_PIN 28    //1 -> 34
#define LED_1_PIN 27    //2 -> 32
#define LED_2_PIN 26    //3 -> 31
#define LED_3_PIN 22    //4 -> 29
#define LED_4_PIN 21    //5 -> 27
#define LED_5_PIN 20    //6 -> 26
#define LED_6_PIN 19    //7 -> 25
#define LED_7_PIN 18    //8 -> 24
#define LED_8_PIN 17    //9 -> 22
#define LED_9_PIN 16    //10 -> 21

// ===== Potentiometer Pin =====
#define POT_DT_PIN 3    // pin 5
#define POT_SW_PIN 4    // pin 6