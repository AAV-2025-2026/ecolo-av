// A stand-in for the firmware's globals.h: the same names, with no WiFi or web server,
// then the real hardware_configs.h (its pins and Jrk and DAC constants).
#pragma once
#include <Arduino.h>
#include <JrkG2.h>

struct WebServer {};
struct HTTPUpdateServer {};
struct WebSocketsServer {};
struct IBusBM {};
struct PCA9555 {};

#include "hardware_configs.h"
