#include "UDPClient.hpp"
#include <cstddef>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <cstdint>
#include <string>
#include <sys/types.h>
#include <unistd.h>
#include <vector>


UDPClient::UDPClient(const std::string& ipAddr, uint16_t portNumber) : m_portNumber(portNumber) {
    m_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (m_socket < 0) {
        std::cerr << "Could not open socket!" << std::endl;
        throw std::runtime_error("Couldn't create socket");
    }

    // 0 initialize struct
    std::memset(&m_serverAddress, 0, sizeof(m_serverAddress));
    m_serverAddress.sin_family = AF_INET;
    m_serverAddress.sin_port = htons(m_portNumber);

    if (inet_pton(AF_INET, ipAddr.c_str(), &m_serverAddress.sin_addr) <= 0) {
        close(m_socket);
        throw std::runtime_error("Invalid IP Address");
    }
}

UDPClient::~UDPClient() {
    if (m_socket >= 0) {
        close(m_socket);
    }
}

bool UDPClient::sendData(std::vector<char>& data) {
    ssize_t sent = sendto(
        m_socket, 
        data.data(), 
        data.size(), 
        0, 
        reinterpret_cast<struct sockaddr*>(&m_serverAddress), 
        sizeof(m_serverAddress)
    );
    std::cout << "UDP Client sent this data of this size: " << sent << std::endl;

    return static_cast<size_t>(sent) == data.size();
}

std::vector<uint8_t> UDPClient::receiveData(size_t length) {
    std::vector<uint8_t> data;
    data.resize(length);
    
    socklen_t addressLength = sizeof(m_serverAddress);

    size_t receivedLength = recvfrom(
        m_socket, 
        data.data(), 
        length, 
        0, 
        reinterpret_cast<struct sockaddr*>(&m_serverAddress), 
        &addressLength
    );
    data.resize(receivedLength);

    return data;
}