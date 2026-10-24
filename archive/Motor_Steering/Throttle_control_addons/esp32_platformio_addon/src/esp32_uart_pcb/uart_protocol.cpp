\
#include "uart_protocol.h"

uint16_t crc16_ccitt_false(const uint8_t* data, size_t len) {
  const uint16_t poly = 0x1021;
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (int b = 0; b < 8; b++) {
      if (crc & 0x8000) crc = (uint16_t)((crc << 1) ^ poly);
      else             crc = (uint16_t)(crc << 1);
    }
  }
  return crc;
}

static uint16_t u16_le(const uint8_t* p) {
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static int16_t i16_le(const uint8_t* p) {
  return (int16_t)u16_le(p);
}

bool parse_uart_frame(const uint8_t* buf, size_t len, UartCmd& out) {
  if (len != UART_FRAME_LEN) return false;
  if (buf[0] != UART_START1 || buf[1] != UART_START2) return false;
  if (buf[2] != UART_VERSION) return false;

  uint16_t crc_rx = u16_le(&buf[11]);
  uint16_t crc_calc = crc16_ccitt_false(buf, 11);
  if (crc_rx != crc_calc) return false;

  uint8_t flags = buf[4];

  out.seq = buf[3];
  out.armed = (flags & FLAG_ARMED) != 0;
  out.estop = (flags & FLAG_ESTOP) != 0;
  out.dir_fwd = (flags & FLAG_DIR_FWD) != 0;

  out.steer_cmd = i16_le(&buf[5]);
  out.throttle_cmd = u16_le(&buf[7]);
  out.brake_cmd = u16_le(&buf[9]);
  return true;
}
