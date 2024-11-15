#include "hardware_config.h"
#include "hardware_fns.h"

extern Adafruit_MCP4725 dac;

void hardware_setup(){
    pinMode(LED_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);


    Serial.println(dac.begin(0x62));
}
