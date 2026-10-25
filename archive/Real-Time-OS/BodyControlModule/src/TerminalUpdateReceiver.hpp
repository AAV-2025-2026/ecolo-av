#ifndef TERMINAL_UPDATE_RECEIVER
#define TERMINAL_UPDATE_RECEIVER

#include "UpdateReceiver.hpp"
#include "VehicleState.hpp"
#include <memory>
#include <thread>

class TerminalUpdateReceiver : public UpdateReceiver {
public:
    TerminalUpdateReceiver(std::shared_ptr<VehicleState> vehicleState) : UpdateReceiver(vehicleState) {}
    void start() override;
    void stop() override;
    ~TerminalUpdateReceiver() override;

private:
    std::thread m_consoleThread;

};

#endif