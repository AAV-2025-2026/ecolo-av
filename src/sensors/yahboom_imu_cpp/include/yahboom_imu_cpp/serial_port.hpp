#pragma once
#include <string>
#include <cstdint>

class SerialPort
{
public:
  SerialPort(const std::string & port, int baud_rate);
  ~SerialPort();
  int readByte(uint8_t & byte);
  int readBytes(uint8_t * buffer, int len);
  bool isOpen() const {return fd_ >= 0;}

private:
  int fd_ = -1;
  int toBaudRate(int baud);    // return int instead of speed_t
};
