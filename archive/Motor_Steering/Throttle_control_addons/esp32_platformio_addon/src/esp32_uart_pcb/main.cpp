\
#include <Arduino.h>
#include <Wire.h>
#include <JrkG2.h>

#include "../esp32_ros_pcb/hardware_config.h"
#include "../esp32_ros_pcb/motor_ctrl/MotorCtrl.h"
#include "../esp32_ros_pcb/rc.h"

#include "uart_protocol.h"

// Jrk IDs match your existing config
JrkG2I2C jrk_steer(STEER_ID);
JrkG2I2C jrk_brake(BRAKE_ID);

// ---------------------- UART link ----------------------
static HardwareSerial& PI_SERIAL = ROS_SERIAL;   // reuse Serial1 from your config
static const uint32_t PI_BAUD = 115200;
static const uint32_t LINK_TIMEOUT_MS = 250;     // if no good frame received -> safe stop

// Direction pin level semantics
static const bool DIR_FWD_LEVEL = LOW;           // many setups use LOW for forward; change if needed

// Steering mapping / limits
static const uint16_t STEER_CENTER = 2048;
static int g_max_steer_delta = 700;              // clamp around center to prevent hard steering

// Safety caps
static uint16_t g_max_throttle = 250;            // DAC units 0..1023
static uint16_t g_max_brake = 4095;              // Jrk target 0..4095

static uint32_t g_last_ok_ms = 0;

// Fixed-length receive buffer
static uint8_t rxbuf[UART_FRAME_LEN];
static size_t rxidx = 0;

// ---------------------- Helpers ----------------------
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
  // steer_cmd expected ~[-2000..2000]
  int cmd = (int)steer_cmd;
  cmd = clamp_i(cmd, STEER_READ_MIN, STEER_READ_MAX);
  // map -2000..2000 -> 0..4095
  long target = map((long)cmd, (long)STEER_READ_MIN, (long)STEER_READ_MAX, 0L, 4095L);

  // apply limit around center
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

    // Find start bytes
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
        digitalWrite(LED_PIN, HIGH);
        delayMicroseconds(200);
        digitalWrite(LED_PIN, LOW);
      }
    }
  }
}

void setup() {
  USER_SERIAL.begin(115200);
  delay(200);

  pinMode(LED_PIN, OUTPUT);
  pinMode(BLUE_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);
  digitalWrite(BLUE_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(GREEN_LED_PIN, LOW);

  USER_SERIAL.println();
  USER_SERIAL.println("ESP32 UART actuator starting (no micro-ROS).");

  hardware_setup();

  // Start PI UART (Serial1)
  PI_SERIAL.begin(PI_BAUD, SERIAL_8N1, RX_PIN, TX_PIN);  
  g_last_ok_ms = millis();

  safe_stop_outputs();
  set_dir(true);

  USER_SERIAL.println("Ready. Waiting for UART frames from Pi...");
}

void loop() {
  uart_rx_step();

  // Link watchdog
  if (millis() - g_last_ok_ms > LINK_TIMEOUT_MS) {
    safe_stop_outputs();
  }

  delay(2);
}
