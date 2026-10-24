#ifndef UPDATE_RECEIVER_HPP
#define UPDATE_RECEIVER_HPP

#include "VehicleState.hpp"
#include <memory>
#include <atomic>

class UpdateReceiver {
public:
    UpdateReceiver(std::shared_ptr<VehicleState> vehicleState) : m_vehicleState(vehicleState), m_running(false) {}
    UpdateReceiver(const UpdateReceiver&) = delete;
    UpdateReceiver(UpdateReceiver&&) = delete;
    virtual ~UpdateReceiver() = default;
    virtual void start() { m_running = true; }
    virtual void stop() { m_running = false; }

protected:
    std::shared_ptr<VehicleState> m_vehicleState;
    std::atomic_bool m_running;
};

#endif