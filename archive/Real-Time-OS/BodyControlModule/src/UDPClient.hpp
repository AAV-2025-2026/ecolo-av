#ifndef UDP_CLIENT_HPP
#define UDP_CLIENT_HPP

#include <arpa/inet.h>
#include <cstdint>
#include <sys/types.h>
#include <vector>
#include <string>


class UDPClient {
public:
    UDPClient(const std::string& ipAddr, uint16_t portNumber);
    ~UDPClient();

    bool sendData(std::vector<char>& data);
    std::vector<uint8_t> receiveData(size_t length);
private:
    uint16_t m_portNumber;
    int m_socket;
    struct sockaddr_in m_serverAddress;
};

#endif