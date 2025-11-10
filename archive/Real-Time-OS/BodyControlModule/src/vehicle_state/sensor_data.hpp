#ifndef SENSOR_DATA_HPP
#define SENSOR_DATA_HPP

namespace vehicle_state {

/**
 * Definitions of structs that hold various types of sensor data
 */

struct SpeedData {
    double speed;
};

struct DirectionData {
    double heading; // Subject to change // Degrees from north
};

struct LocationData {
    double latitude, longitude;
};


} // namespace vehicle_state

#endif
