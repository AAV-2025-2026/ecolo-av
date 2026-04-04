#include <chrono>
#include <cstdint>
#include <iostream>
#include "UDPClient.hpp"
#include "UDPUpdateReceiver.hpp"
#include "VehicleState.hpp"
#include <memory>
#include <thread>
#include "TerminalUpdateReceiver.hpp"

constexpr const char* SUBSCRIBER_IP = "192.168.1.104";
constexpr const uint16_t SUBSCRIBER_PORT_NUMBER = 49200;
constexpr const char* PUBLISHER_IP = "192.168.1.104";
constexpr const uint16_t PUBLISHER_PORT_NUMBER = 49200;

int main() {
    std::cout << "Hello QNX!" << std::endl;

    auto subscriber = std::make_shared<UDPClient>(SUBSCRIBER_IP, SUBSCRIBER_PORT_NUMBER);
    auto publisher = std::make_shared<UDPClient>(PUBLISHER_IP, PUBLISHER_PORT_NUMBER);

    std::shared_ptr<VehicleState> vehicleState = std::make_shared<VehicleState>(publisher);

    TerminalUpdateReceiver updateReciver(vehicleState);
    updateReciver.start();

    UDPUpdateReceiver subscriberReceiver(vehicleState, subscriber);
    subscriberReceiver.start();

    while(true) {
        vehicleState->printState();
        std::this_thread::sleep_for(std::chrono::seconds(10));
    }

    updateReciver.stop();

    return 0;
}
