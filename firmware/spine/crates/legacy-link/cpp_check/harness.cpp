// Runs the 2025-26 team's own ros2_handler.cpp and jrk_g2.cpp on a laptop, and prints what
// they send to the devices for each frame. tools/tests/test_legacy_cpp.py compiles it with
// the stubs beside it, and checks the output against legacy-link's vectors.json.
//
// Input, on stdin: one frame a line, 13 hex bytes.
// Output: one line a frame: "<steering target> <brake target> <throttle>", where the
// throttle is "cut", "idle", "drive <code> <fwd|rev>", or the whole line is "rejected".
#include <cstdio>
#include <string>
#include <vector>

#include "dac/dac.h"
#include "globals.h"
#include "ros2_handler/ros2_handler.h"
#include "websoc_serial/websoc_serial.h"

FakeSerial Serial1;
FakeWire Wire;
QuietLog WSerial;

// main.cpp's globals that the two files use.
JrkG2I2C jrk_steer(STEER_ID);
JrkG2I2C jrk_brake(BRAKE_ID);
bool jrk_steer_ok = true;
bool jrk_brake_ok = true;
float current_steering = 0, current_speed = 0, current_accel = 0;
uint32_t current_dac = 0;

// What one frame did.
static int steer = -1, brake = -1, dac_cut = 0, dac_ramp = -1, dir = -1;

void record_jrk_target(uint8_t address, uint16_t target) {
    if (address == STEER_ID) steer = target;
    if (address == BRAKE_ID) brake = target;
}

// dac.cpp's functions, recorded: the ramp's target is what matters here.
void writeDAC(uint16_t value) {
    if (value == 0) dac_cut = 1;
}
void writeDACRamped(uint16_t target) { dac_ramp = target; }
void ext_digitalWrite(uint8_t pin, bool value) {
    if (pin == DIR_PIN) dir = value;
}

int main() {
    char line[256];
    while (std::fgets(line, sizeof line, stdin)) {
        std::vector<uint8_t> bytes;
        unsigned v;
        int used;
        for (const char* p = line; std::sscanf(p, "%x%n", &v, &used) == 1; p += used)
            bytes.push_back(static_cast<uint8_t>(v));
        steer = brake = dac_ramp = dir = -1;
        dac_cut = 0;
        uint8_t buf[13];
        uint8_t idx = 0;
        Serial1 = FakeSerial{bytes.data(), static_cast<int>(bytes.size()), 0};
        handleROS2Messages(buf, idx);
        if (steer < 0) {
            std::printf("rejected\n");
        } else if (dac_cut) {
            std::printf("%d %d cut\n", steer, brake);
        } else if (dac_ramp == 0) {
            std::printf("%d %d idle\n", steer, brake);
        } else {
            std::printf("%d %d drive %d %s\n", steer, brake, dac_ramp, dir ? "fwd" : "rev");
        }
    }
    return 0;
}
