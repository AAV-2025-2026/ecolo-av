#ifndef MESSAGE_STRUCTURES_HPP
#define MESSAGE_STRUCTURES_HPP

#include <cstdint>

enum class SubscriberMessageType : uint8_t {
    GPS = 0,
    IMU = 1
};

struct GPSData {
    double longitude, latitude, altitude;
};

struct IMUData {
    float ang_vel_x, ang_vel_y, ang_vel_z;
    float lin_acc_x, lin_acc_y, lin_acc_z;
};

enum class PublisherMessageType : uint8_t {
    LOCATION = 0,
    SPEED = 1,
    GEAR = 2
};

#pragma pack(push, 1)
template<typename T>
struct PublisherMessage {
    PublisherMessageType mType;
    T data;
};
#pragma pack(pop)

#endif
