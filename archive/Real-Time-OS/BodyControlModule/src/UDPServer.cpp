#include "UDPServer.hpp"
#include <cstdint>
#include <cstring>
#include <netinet/in.h>
#include <stdexcept>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <sys/types.h>
#include <unistd.h>
#include <vector>

UDPServer::UDPServer(uint16_t portNumber) : m_portNumber(portNumber) {
    m_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (m_socket < 0) {
        throw std::runtime_error("Failed to create socket");
    }

    std::memset(&m_serverAddress, 0, sizeof(m_serverAddress));
    m_serverAddress.sin_family = AF_INET;
    m_serverAddress.sin_addr.s_addr = INADDR_ANY;
    m_serverAddress.sin_port = htons(m_portNumber);

    if (bind(m_socket, reinterpret_cast<struct sockaddr*>(&m_serverAddress), sizeof(m_serverAddress)) < 0) {
        close(m_socket);
        throw std::runtime_error("Bind failed");
    }
}

UDPServer::~UDPServer() {
    if (m_socket >= 0) {
        close(m_socket);
    }
}

std::vector<uint8_t> UDPServer::receiveData(size_t length, sockaddr_in& clientAddress) {
    std::vector<uint8_t> data;
    data.resize(length);

    socklen_t addressLength = sizeof(clientAddress);

    size_t receivedLength = recvfrom(
        m_socket, 
        data.data(), 
        data.size(), 
        0, 
        reinterpret_cast<struct sockaddr*>(&clientAddress), 
        &addressLength
    );
    data.resize(receivedLength);

    return data;
}

bool UDPServer::sendData(std::vector<uint8_t>& data, const sockaddr_in& clientAddress) {
    ssize_t sent = sendto(
        m_socket, 
        data.data(), 
        data.size(), 
        0, 
        reinterpret_cast<const struct sockaddr*>(&clientAddress), 
        sizeof(clientAddress)
    );

    return static_cast<size_t>(sent) == data.size();
}