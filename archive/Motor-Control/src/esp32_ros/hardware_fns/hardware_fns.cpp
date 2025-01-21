#include "hardware_config.h"
#include "hardware_fns.h"

extern Adafruit_MCP4725 dac;

void hardware_setup(){


    pinMode(BLUE_LED_PIN, OUTPUT);
    pinMode(RED_LED_PIN, OUTPUT);
    pinMode(GREEN_LED_PIN, OUTPUT);

    digitalWrite(BLUE_LED_PIN, HIGH);
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(GREEN_LED_PIN, HIGH);

    pinMode(LED_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);

    bool begin = false;
    while(!begin){
        digitalWrite(RED_LED_PIN, LOW);
        delay(100);
        USER_SERIAL.println("CONNECTING TO DAC i2C");
        begin = dac.begin(0x62);
        if(!begin){
            USER_SERIAL.println("DAC CONNECTION FAIL");
        }
        //set write EEPROM
        dac.setVoltage(0,true);
        delay(250);
        digitalWrite(RED_LED_PIN, HIGH);
        delay(250);
    }

    USER_SERIAL.println("DAC CONNECTION SUCCESS");

    
}


// Function to read a channel and map its value to a given range
int readChannel(int channelInput, int minLimit, int maxLimit, int defaultValue) {
    int ch = pulseIn(channelInput, HIGH, 30000); // Read PWM signal
    if (ch < 100) return defaultValue; // Default value if signal is invalid
    return map(ch, 1000, 2000, minLimit, maxLimit);
}

// Read the switch channel and return a boolean value
bool readSwitch(byte channelInput, bool defaultValue){
  int intDefaultValue = (defaultValue)? 100: 0;
  int ch = readChannel(channelInput, 0, 100, intDefaultValue);
  return (ch > 50);
}