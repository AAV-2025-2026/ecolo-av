#include "UpdateSender.hpp"
#include "MessageStructures.hpp"
#include "StateStructures.hpp"
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <memory>
#include <mqueue.h>
#include <string>
#include <thread>
#include "dbstruct.h"
#include "UDPClient.hpp"
#include <string.h>
#include <vector>

bool sendDBMsg(const mqd_t& mq, std::string_view tableName, std::string_view id, const std::vector<char> &data, const unsigned int priority) {
    DB_t msg;

    if (data.size() > sizeof(msg.table) || tableName.size() > sizeof(msg.table) || id.size() > sizeof(msg.id)) {
        std::cerr << "Attempting to send too much data in mqueue" << std::endl;
        return false;
    }

    strncpy(msg.table, tableName.data(), sizeof(msg.table));
    strncpy(msg.id, id.data(), sizeof(msg.id));
    strncpy(msg.msg, data.data(), sizeof(msg.msg));

    int rc = mq_send(mq, reinterpret_cast<char *>(&msg), sizeof(msg), priority);
    if (rc == -1) {
        char * error = strerror(errno);
        std::cerr << "Failed to send data: \n" << std::string(data.data()) << "\n to table: " << tableName << " with ID: " << id << "\n";
        std::cerr << "Error code: " << error << std::endl;
        return false;
    }

    std::cout << "Successfully sent data: \n" << std::string(data.data()) << "\n to table: " << tableName << " with ID: " << id << std::endl;
    return true;
}

UpdateSender::UpdateSender(std::shared_ptr<UDPClient> publisher) : m_publisher(publisher) {
    // Setup MQueue stuff
    std::cout << "Trying to open mqueue" << std::endl;
    while (true) {
        m_mqueue = mq_open(DB_MQUEUE_NAME, O_WRONLY | O_NONBLOCK);
        if (m_mqueue != static_cast<mqd_t>(-1)) {
            break;
        }
        std::cerr << "Could not open mqueue. ";
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        std::cerr << "Trying to open mqueue again" << std::endl;
    }
    std::cout << "mqueue successfully opened\n";
}

bool UpdateSender::updateSpeed(const SpeedState& newSpeed) {
    bool success = true;
    if (!updateSpeedDB(newSpeed)) {
        std::cerr << "Failed to update the database with a new speed value" << std::endl;
        success = false;
    }
    if (!updateSpeedROS(newSpeed)) {
        std::cerr << "Failed to update ROS with a new speed value" << std::endl;
        success = false;
    } else {
        std::cout << "Successfully updated speed with ROS" << std::endl;
    }
    return success;
}

bool UpdateSender::updateSpeedDB(const SpeedState& newSpeed) {
    std::string speedString = "Speed: " + std::to_string(newSpeed.speed);
    std::vector<char> data(speedString.begin(), speedString.end());
    data.push_back('\0');

    return sendDBMsg(m_mqueue, DB_TABLE_NAME, DB_ID_NAME, data, MQ_PRIORITY);
}

bool UpdateSender::updateSpeedROS(const SpeedState& newSpeed) {
    PublisherMessage<SpeedState> message;
    message.mType = PublisherMessageType::SPEED;
    message.data = newSpeed;

    std::vector<char> data(sizeof(message));
    std::memcpy(data.data(), &message, sizeof(message));
    return m_publisher->sendData(data);
}

bool UpdateSender::updateLocation(const LocationState& newLocation) {
    bool success = true;
    if (!updateLocationDB(newLocation)) {
        std::cerr << "Failed to update the database with a new location value" << std::endl;
        success = false;
    }
    if (!updateLocationROS(newLocation)) {
        std::cerr << "Failed to update ROS with a new location value" << std::endl;
        success = false;
    }
    return success;
}

bool UpdateSender::updateLocationDB(const LocationState& newLocation) {
    std::string locationString = "Location: x: " + std::to_string(newLocation.x) + ", y: " + std::to_string(newLocation.y);
    std::vector<char> data(locationString.begin(), locationString.end());
    data.push_back('\0');

    return sendDBMsg(m_mqueue, DB_TABLE_NAME, DB_ID_NAME, data, MQ_PRIORITY);
}

bool UpdateSender::updateLocationROS(const LocationState& newLocation) {
    PublisherMessage<LocationState> message;
    message.mType = PublisherMessageType::LOCATION;
    message.data = newLocation;

    std::vector<char> data(sizeof(message));
    std::memcpy(data.data(), &message, sizeof(message));
    return m_publisher->sendData(data);
}

bool UpdateSender::updateGear(const Gear& newGear) {
    bool success = true;
    if (!updateGearROS(newGear)) {
        std::cerr << "Failed to update ROS with a new Gear value" << std::endl;
        success = false;
    }
    return success;
}

bool UpdateSender::updateGearROS(const Gear& newGear) {
    PublisherMessage<Gear> message;
    message.mType = PublisherMessageType::GEAR;
    message.data = newGear;

    std::vector<char> data(sizeof(message));
    std::memcpy(data.data(), &message, sizeof(message));
    return m_publisher->sendData(data);
}
