#include "hardware_config.h"
#include "hardware_fns.h"

extern Adafruit_MCP4725 dac;

void hardware_setup(){
    Serial.println("setup1");
    pinMode(LED_PIN, OUTPUT);
    Serial.println("setup2");
    pinMode(DIR_PIN, OUTPUT);
    Serial.println("setup3");


    Serial.println(dac.begin(0x62));
    Serial.println("setup4");

    
}
