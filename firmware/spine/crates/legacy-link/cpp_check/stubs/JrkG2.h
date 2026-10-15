// A stand-in for Pololu's JrkG2 library: records each target, for harness.cpp.
#pragma once
#include <cstdint>

void record_jrk_target(uint8_t address, uint16_t target);

class JrkG2I2C {
public:
    explicit JrkG2I2C(uint8_t address) : address_(address) {}
    void setTarget(uint16_t target) { record_jrk_target(address_, target); }
    uint16_t getErrorFlagsHalting() { return 0; }

private:
    uint8_t address_;
};
