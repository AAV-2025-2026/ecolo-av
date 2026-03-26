#ifndef MESSAGE_STRUCTURE_HPP
#define MESSAGE_STRUCTURE_HPP

enum class PublisherMessageType : uint8_t {
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

enum class SubscriberMessageType : uint8_t {
    GPS = 0,
    IMU = 1
};

#pragma pack(push, 1)
struct IMUPacket{
  SubscriberMessageType message_type = SubscriberMessageType::IMU;
  float ang_vel_x;
  float ang_vel_y;
  float ang_vel_z;
  float lin_acc_x;
  float lin_acc_y;
  float lin_acc_z;
};
#pragma pack(pop)

#pragma pack(push, 1)
struct GPSPacket {
  SubscriberMessageType message_type = SubscriberMessageType::GPS;
  double latitude;
  double longitude;
  double altitude;
};
#pragma pack(pop)

#endif
