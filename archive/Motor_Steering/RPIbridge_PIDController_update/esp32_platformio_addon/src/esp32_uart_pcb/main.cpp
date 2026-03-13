#include <Arduino.h>
#include <Wire.h>
#include <JrkG2.h>

#include "../esp32_ros_pcb/hardware_config.h"
#include "../esp32_ros_pcb/motor_ctrl/MotorCtrl.h"
#include "../esp32_ros_pcb/rc.h"

#include "uart_protocol.h"

JrkG2I2C jrk_steer(STEER_ID);
JrkG2I2C jrk_brake(BRAKE_ID);

static HardwareSerial& PI_SERIAL = ROS_SERIAL;
static const uint32_t PI_BAUD = 115200;
static const uint32_t LINK_TIMEOUT_MS = 250;
static const bool DIR_FWD_LEVEL = LOW;
static const uint16_t STEER_CENTER = 2048;
static int g_max_steer_delta = 700;
static uint16_t g_max_throttle = 250;
static uint16_t g_max_brake = 4095;
static uint32_t g_last_ok_ms = 0;
static uint8_t rxbuf[UART_FRAME_LEN];
static size_t rxidx = 0;

static inline int clamp_i(int v, int lo, int hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

static inline uint16_t clamp_u16(int v, int lo, int hi) {
  if (v < lo) return (uint16_t)lo;
  if (v > hi) return (uint16_t)hi;
  return (uint16_t)v;
}

static void safe_stop_outputs() {
  writeDAC(0);
  jrk_brake.setTarget(0);
}

static void set_dir(bool dir_fwd) {
  ext_digitalWrite(DIR_PIN, (dir_fwd ? DIR_FWD_LEVEL : !DIR_FWD_LEVEL));
}

static void set_steer_from_cmd(int16_t steer_cmd) {
  int cmd = clamp_i((int)steer_cmd, STEER_READ_MIN, STEER_READ_MAX);
  long target = map((long)cmd, (long)STEER_READ_MIN, (long)STEER_READ_MAX, 0L, 4095L);
  int delta = (int)target - (int)STEER_CENTER;
  delta = clamp_i(delta, -g_max_steer_delta, g_max_steer_delta);
  uint16_t limited = (uint16_t)((int)STEER_CENTER + delta);
  jrk_steer.setTarget(limited);
}

static void apply_cmd(const UartCmd& cmd) {
  if (cmd.estop || !cmd.armed) {
    safe_stop_outputs();
    return;
  }

  set_dir(cmd.dir_fwd);
  set_steer_from_cmd(cmd.steer_cmd);

  uint16_t thr = clamp_u16((int)cmd.throttle_cmd, 0, (int)g_max_throttle);
  uint16_t brk = clamp_u16((int)cmd.brake_cmd, 0, (int)g_max_brake);

  if (brk > 0) {
    writeDAC(0);
    jrk_brake.setTarget(brk);
  } else {
    jrk_brake.setTarget(0);
    writeDAC(thr);
  }
}

static void uart_rx_step() {
  while (PI_SERIAL.available() > 0) {
    uint8_t b = (uint8_t)PI_SERIAL.read();

    if (rxidx == 0) {
      if (b != UART_START1) continue;
      rxbuf[rxidx++] = b;
      continue;
    }
    if (rxidx == 1) {
      if (b != UART_START2) { rxidx = 0; continue; }
      rxbuf[rxidx++] = b;
      continue;
    }

    rxbuf[rxidx++] = b;
    if (rxidx >= UART_FRAME_LEN) {
      UartCmd cmd{};
      bool ok = parse_uart_frame(rxbuf, UART_FRAME_LEN, cmd);
      rxidx = 0;
      if (ok) {
        g_last_ok_ms = millis();
        apply_cmd(cmd);
      }
    }
  }
}

void setup() {
  USER_SERIAL.begin(115200);
  delay(200);
  hardware_setup();
  PI_SERIAL.begin(PI_BAUD);
  g_last_ok_ms = millis();
  safe_stop_outputs();
  set_dir(true);
}

void loop() {
  uart_rx_step();
  if (millis() - g_last_ok_ms > LINK_TIMEOUT_MS) {
    safe_stop_outputs();
  }
  delay(2);
}
