#include "VehicleState.hpp"
#include "MessageStructures.hpp"
#include "StateStructures.hpp"
#include "UDPClient.hpp"
#include "UpdateSender.hpp"
#include <iostream>
#include <memory>
#include <optional>
#include <mutex>
#include <cmath>

VehicleState::VehicleState(std::shared_ptr<UDPClient> updatePublisher) {
    m_updater = std::make_shared<UpdateSender>(updatePublisher);
}

bool VehicleState::imuUpdate(const IMUData& imuData) {
    SpeedState newSpeed;
    // Speed = sqrt(x^2 + y^2 + z^2)
    double acc_magnitude = std::sqrt(imuData.lin_acc_x * imuData.lin_acc_x +
                                     imuData.lin_acc_y * imuData.lin_acc_y +
                                     imuData.lin_acc_z * imuData.lin_acc_z);
    newSpeed.speed = acc_magnitude;
    
    Gear newGear;
    if (acc_magnitude > 0) {
        newGear = Gear::Drive;
    } else if (acc_magnitude < 0) {
        newGear = Gear::Reverse;
    } else {
        newGear = Gear::Park;
    }

    return setSpeed(newSpeed) && setGear(newGear);
}

bool VehicleState::setSpeed(const SpeedState& newSpeed) {
    std::lock_guard lock(m_mutex);
    m_speed = newSpeed;
    std::cout << "Vehicle Speed State updated to: " << m_speed->getData().speed << std::endl;
    return m_updater->updateSpeed(m_speed->getData());
}

bool VehicleState::setGear(const Gear& newGear) {
    std::lock_guard lock(m_mutex);
    m_gear = newGear;
    std::cout << "Vehicle Gear State updated to: " << m_gear->getData() << std::endl;
    return m_updater->updateGear(m_gear->getData());
}

bool VehicleState::gpsUpdate(const GPSData& gpsData) {
    LocationState newLocation;
    newLocation.x = gpsData.longitude;
    newLocation.y = gpsData.latitude;
    return setLocation(newLocation);
}

bool VehicleState::setLocation(const LocationState& newLocation) {
    std::lock_guard lock(m_mutex);
    m_location = newLocation;
    std::cout << "Vehicle Location State updated to: " << "x: " << m_location->getData().x << ", y: " << m_location->getData().y << std::endl;
    return m_updater->updateLocation(m_location->getData());
}

void VehicleState::printState() {
    std::cout << "The current state is: ";

    std::cout << "Speed: ";
    if (m_speed.has_value()) {
        std::cout << m_speed->getData().speed;
    } else {
        std::cout << "unintitalized speed";
    }
    std::cout << ", ";

    std::cout << "Location: ";
    if (m_location.has_value()) {
        std::cout << "x: " << m_location->getData().x << ", y: " << m_location->getData().y;
    } else {
        std::cout << "uninitialized location";
    }
    std::cout << ", ";

    std::cout << "Gear: ";
    if (m_gear.has_value()) {
        std::cout << m_gear->getData();
    } else {
        std::cout << "uninitialized gear";
    }

    std::cout << std::endl;
}
