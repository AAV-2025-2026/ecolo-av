// A stand-in for the firmware's log (USB serial and a WebSocket): it prints nothing.
#pragma once

struct QuietLog {
    void println(const char*) {}
    template <typename... Args>
    void printf(const char*, Args...) {}
};
extern QuietLog WSerial;
#define USER_SERIAL WSerial
