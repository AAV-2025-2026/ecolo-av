#ifndef UDP_UPDATE_RECEIVER_HPP
#define UDP_UPDATE_RECEIVER_HPP

#include "UDPClient.hpp"
#include "UpdateReceiver.hpp"
#include <cstddef>
#include <memory>
#include <thread>

class UDPUpdateReceiver : public UpdateReceiver {
public:
    UDPUpdateReceiver(std::shared_ptr<VehicleState> vehicleState, std::shared_ptr<UDPClient> subsciber);
    void start();
    void stop();

private:
    static constexpr const size_t MAX_RECEIVE_LENGTH = 4096;

    std::thread m_receiverThread;
    std::shared_ptr<UDPClient> m_subscriber;
};

#endif