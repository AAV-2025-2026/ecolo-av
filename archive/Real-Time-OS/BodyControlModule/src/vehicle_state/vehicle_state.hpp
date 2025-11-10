#ifndef VEHICLE_STATE_HPP
#define VEHICLE_STATE_HPP

#include <chrono>
#include <optional>
#include <utility>
#include "sensor_data.hpp"

namespace vehicle_state {
using namespace std::chrono;

/**
 * Sensor Data we want to record
 */
class VehicleState {
public:
    VehicleState();
    ~VehicleState();

    void setSpeed(const SpeedData& value);
    void setDirection(const DirectionData& value);
    void setLocation(const DirectionData& value);

    std::optional<std::pair<time_point<steady_clock>, SpeedData>> getSpeed();
    std::optional<std::pair<time_point<steady_clock>, DirectionData>> getDirection();
    std::optional<std::pair<time_point<steady_clock>, LocationData>> getLocation();
private:
    std::optional<std::pair<time_point<steady_clock>, SpeedData>> m_speed;
    std::optional<std::pair<time_point<steady_clock>, DirectionData>> m_direction;
    std::optional<std::pair<time_point<steady_clock>, LocationData>> m_location;
};


}

#endif
