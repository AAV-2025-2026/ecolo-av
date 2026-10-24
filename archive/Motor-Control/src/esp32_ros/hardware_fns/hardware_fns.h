

#ifndef AAV_HARDWARE_FNS_H
#define AAV_HARDWARE_FNS_H

#include "./hardware_config.h"
#include <Adafruit_MCP4725.h>

void hardware_setup();

int readChannel(int channelInput, int minLimit, int maxLimit, int defaultValue);
bool readSwitch(byte channelInput, bool defaultValue);


#endif