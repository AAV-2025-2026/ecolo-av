#ifndef VEHICLE_STATE_HPP
#define VEHICLE_STATE_HPP

#include <optional>
#include "MessageStructures.hpp"
#include "StateStructures.hpp"
#include "UpdateSender.hpp"
#include <memory>
#include <mutex>

class VehicleState {
public:
    VehicleState(std::shared_ptr<UDPClient> updatePublisher);

    bool imuUpdate(const IMUData& imuData);
    bool setSpeed(const SpeedState& newSpeed);
    bool setGear(const Gear& newGear);
    std::optional<StateObject<SpeedState>> getSpeed() {return m_speed;}
    std::optional<StateObject<Gear>> getGear() {return m_gear;}

    bool gpsUpdate(const GPSData& gpsData);
    bool setLocation(const LocationState& newLocation);
    std::optional<StateObject<LocationState>> getLocation() {return m_location;}

    void printState();

private:
    std::shared_ptr<UpdateSender> m_updater;

    std::mutex m_mutex;

    std::optional<StateObject<SpeedState>> m_speed;
    std::optional<StateObject<LocationState>> m_location;
    std::optional<StateObject<Gear>> m_gear;
};

#endif
