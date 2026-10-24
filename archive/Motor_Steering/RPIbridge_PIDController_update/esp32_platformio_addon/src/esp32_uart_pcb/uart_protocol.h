#pragma once
#include <stdint.h>
#include <stddef.h>

static const uint8_t UART_START1 = 0xAA;
static const uint8_t UART_START2 = 0x55;
static const uint8_t UART_VERSION = 0x01;
static const size_t UART_FRAME_LEN = 13;

static const uint8_t FLAG_ARMED = 1 << 0;
static const uint8_t FLAG_ESTOP = 1 << 1;
static const uint8_t FLAG_DIR_FWD = 1 << 2;

struct UartCmd {
  uint8_t seq;
  bool armed;
  bool estop;
  bool dir_fwd;
  int16_t steer_cmd;
  uint16_t throttle_cmd;
  uint16_t brake_cmd;
};

uint16_t crc16_ccitt_false(const uint8_t* data, size_t len);
bool parse_uart_frame(const uint8_t* buf, size_t len, UartCmd& out);
