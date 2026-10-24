#ifndef UPDATE_SENDER_HPP
#define UPDATE_SENDER_HPP

#include "StateStructures.hpp"
#include "UDPClient.hpp"
#include <memory>
#include <vector>
#include <mqueue.h>
#include <string_view>

bool sendDBMsg(const mqd_t& mq, std::string_view tableName, std::string_view id, const std::vector<char>& data, const unsigned int priority);

/**
    This Class Has to update relevant components when the vehicle state is updated
    1. Database through mqueue
    2. ROS Subscribers
        a. Through UDP
*/
class UpdateSender {
public:
    UpdateSender(std::shared_ptr<UDPClient> publisher);
    bool updateSpeed(const SpeedState& newSpeed);
    bool updateGear(const Gear& newGear);
    bool updateLocation(const LocationState& newLocation);

private:
    bool updateSpeedDB(const SpeedState& newSpeed);
    bool updateSpeedROS(const SpeedState& newSpeed);

    bool updateLocationDB(const LocationState& newLocation);
    bool updateLocationROS(const LocationState& newLocation);

    bool updateGearROS(const Gear& newGear);

    static constexpr const char* DB_MQUEUE_NAME = "/db_queue";
    static constexpr const int MQ_PRIORITY = 0;
    static constexpr const char* DB_TABLE_NAME = "states";
    static constexpr const char* DB_ID_NAME = "BCM";

    mqd_t m_mqueue;
    std::shared_ptr<UDPClient> m_publisher;
};

#endif
