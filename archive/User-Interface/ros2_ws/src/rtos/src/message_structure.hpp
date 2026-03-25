#ifndef MESSAGE_STRUCTURE_HPP
#define MESSAGE_STRUCTURE_HPP

enum class MessageType : uint8_t {
    Speed = 0,
    Location = 1,
    Gear = 2
};

struct SpeedStruct {
    double speed;
};

struct LocationStruct {
    double x, y;
};

enum class Gear : uint8_t {
    Park = 0,
    Drive = 1,
    Reverse = 2
};

#endif
