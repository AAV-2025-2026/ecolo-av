#include "TerminalUpdateReceiver.hpp"
#include <iostream>
#include "StateStructures.hpp"

void TerminalUpdateReceiver::start() {
    m_running = true;
    m_consoleThread = std::thread([this]{
        while(m_running) {
            std::cout << "Which value would you like to update: [1] Speed, [2] Location, [3] Gear\n";
            int selection;
            std::cin >> selection;
            switch(selection) {
                case 1: {
                    std::cout << "Please enter new speed value: ";
                    double speed;
                    std::cin >> speed;
                    SpeedState newSpeed;
                    newSpeed.speed = speed;
                    m_vehicleState->setSpeed(newSpeed);
                    break;
                }
                case 2: {
                    std::cout << "Please enter new x value: ";
                    double x;
                    std::cin >> x;
                    std::cout << "Please enter new y value: ";
                    double y;
                    std::cin >> y;
                    LocationState newLocation;
                    newLocation.x = x;
                    newLocation.y = y;
                    m_vehicleState->setLocation(newLocation);
                    break;
                }
                case 3: {
                    std::cout << "Set Gear: [1] Park, [2] Drive, [3] Reverse\n";
                    int gear;
                    std::cin >> gear;
                    if (gear < 1 || gear > 3) {
                        std::cout << "Invalid value inputted\n";
                        break;
                    }
                    Gear newGear{static_cast<uint8_t>(gear - 1)};
                    m_vehicleState->setGear(newGear);
                    break;
                }
                default: {
                    std::cout << "Invalid value inputted\n";
                    break;
                }
            }
        }
    });
}

void TerminalUpdateReceiver::stop() {
    m_running = false;
    if (m_consoleThread.joinable()) {
        m_consoleThread.join();
    }
}

TerminalUpdateReceiver::~TerminalUpdateReceiver() {
    stop();
}
