#ifndef UDP_SERVER_HPP
#define UDP_SERVER_HPP

#include <cstdint>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <vector>

class UDPServer {
public:
    UDPServer(uint16_t portNumber);
    ~UDPServer();
    std::vector<uint8_t> receiveData(size_t length, sockaddr_in& clientAddress);
    bool sendData(std::vector<uint8_t>& data, const sockaddr_in& clientAddress);

private:
    uint16_t m_portNumber;
    int m_socket;
    struct sockaddr_in m_serverAddress;
};

#endif