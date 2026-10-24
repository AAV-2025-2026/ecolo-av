#include <iostream>
#include <string>
#include <arpa/inet.h>
#include <unistd.h>
#include <chrono>
#include <thread>

int main() {
    const char* UDP_IP = "127.0.0.1"; // send to localhost
    const int UDP_PORT = 49200;

    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        std::cerr << "Failed to create socket\n";
        return 1;
    }

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(UDP_PORT);
    inet_pton(AF_INET, UDP_IP, &addr.sin_addr);

    while (true) {
        // Sample IMU-like data: ax ay az gx gy gz
        float ax = 0.1f, ay = 0.2f, az = 9.8f;
        float gx = 0.01f, gy = 0.02f, gz = 0.03f;

        char buffer[128];
        int n = snprintf(buffer, sizeof(buffer), "%.2f %.2f %.2f %.2f %.2f %.2f", 
                         ax, ay, az, gx, gy, gz);

        sendto(sockfd, buffer, n, 0, (struct sockaddr*)&addr, sizeof(addr));
        std::cout << "Sent UDP packet: " << buffer << std::endl;

        std::this_thread::sleep_for(std::chrono::milliseconds(500)); // send twice per second
    }

    close(sockfd);
    return 0;
}
