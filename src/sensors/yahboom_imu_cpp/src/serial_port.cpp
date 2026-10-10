#include "yahboom_imu_cpp/serial_port.hpp"
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <stdexcept>

SerialPort::SerialPort(const std::string& port, int baud_rate) {
    fd_ = open(port.c_str(), O_RDWR | O_NOCTTY | O_SYNC);
    if (fd_ < 0)
        throw std::runtime_error("Failed to open: " + port);

    struct termios tty{};
    tcgetattr(fd_, &tty);
    cfsetispeed(&tty, (speed_t)toBaudRate(baud_rate));
    cfsetospeed(&tty, (speed_t)toBaudRate(baud_rate));

    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
    tty.c_cflag |= (CLOCAL | CREAD);
    tty.c_cflag &= ~(PARENB | PARODD | CSTOPB | CRTSCTS);
    tty.c_iflag &= ~(IXON | IXOFF | IXANY);
    tty.c_lflag = 0;
    tty.c_oflag = 0;
    tty.c_cc[VMIN]  = 11;  // block until 11 bytes available
    tty.c_cc[VTIME] = 10;  // 1 second timeout
    tcsetattr(fd_, TCSANOW, &tty);
}

SerialPort::~SerialPort() {
    if (fd_ >= 0) close(fd_);
}

int SerialPort::readByte(uint8_t& byte) {
    return read(fd_, &byte, 1);
}

int SerialPort::readBytes(uint8_t* buffer, int len) {
    int total = 0;
    while (total < len) {
        int n = read(fd_, buffer + total, len - total);
        if (n <= 0) break;
        total += n;
    }
    return total;
}

int SerialPort::toBaudRate(int baud) {
    switch (baud) {
        case 9600:   return B9600;
        case 115200: return B115200;
#ifdef B921600  // Linux only: macOS stops at B230400. The IMU runs on the car's Linux
        case 921600: return B921600;  // computers; on a Mac this just has to compile.
#endif
        default:     return B9600;
    }
}
