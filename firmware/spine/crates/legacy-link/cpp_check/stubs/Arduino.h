// A stand-in for the Arduino core: only what ros2_handler.cpp and jrk_g2.cpp use, so the
// 2025-26 C++ compiles on a laptop for harness.cpp. Not firmware.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>

using std::max;
using std::min;

#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))
#define HIGH 1
#define LOW 0

inline void delay(unsigned long) {}

// Serial1: the Motor-Pi's UART. harness.cpp fills it.
struct FakeSerial {
    const uint8_t* data = nullptr;
    int len = 0;
    int at = 0;
    int available() { return len - at; }
    int readBytes(uint8_t* out, int n) {
        int k = std::min(n, available());
        std::memcpy(out, data + at, k);
        at += k;
        return k;
    }
};
extern FakeSerial Serial1;

// The I2C bus: only jrkPing() uses it.
struct FakeWire {
    void beginTransmission(uint8_t) {}
    uint8_t endTransmission() { return 0; }
};
extern FakeWire Wire;
