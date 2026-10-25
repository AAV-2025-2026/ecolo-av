#include "UDPUpdateReceiver.hpp"
#include "MessageStructures.hpp"
#include "UDPClient.hpp"
#include <cstdint>
#include <cstring>
#include <memory>
#include <iostream>
#include <vector>
#include "StateStructures.hpp"

UDPUpdateReceiver::UDPUpdateReceiver(std::shared_ptr<VehicleState> vehicleState, std::shared_ptr<UDPClient> subscriber) :
    UpdateReceiver(vehicleState),
    m_subscriber(subscriber) {

}

void UDPUpdateReceiver::start() {
    m_running = true;
    m_receiverThread = std::thread([this] {
        while(m_running) {
            auto inputPacket = m_subscriber->receiveData(MAX_RECEIVE_LENGTH);
            if (inputPacket.size() > 0) {
                SubscriberMessageType messageType = static_cast<SubscriberMessageType>(inputPacket[0]);
                switch (messageType) {
                    case SubscriberMessageType::GPS:
                        std::cout << "Received GPS packet\n";
                        GPSData receivedLocation;
                        std::memcpy(&receivedLocation, static_cast<void *>(&inputPacket[1]), sizeof(receivedLocation));
                        m_vehicleState->gpsUpdate(receivedLocation);
                        break;
                    case SubscriberMessageType::IMU:
                        std::cout << "Received IMU packet\n";
                        IMUData receivedIMU;
                        std::memcpy(&receivedIMU, static_cast<void *>(&inputPacket[1]), sizeof(receivedIMU));
                        m_vehicleState->imuUpdate(receivedIMU);
                        break;
                    default:
                        std::cerr << "Received invalid packet" << std::endl;
                        break;
                }
            }
        }
    });
}

void UDPUpdateReceiver::stop() {
    m_running = false;
}
