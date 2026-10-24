# The Orin's heartbeat, carried to the ESP32 (TODO 50; Ben, 24 Oct: "i want a heartbeat
# coming from the orin and have that travel to the esp32").
#
# The output mux publishes one on /control/<target>/heartbeat for each command it passes
# on to /control/<target>/actuator_cmd: only while its gate is OPEN, so the counter stops
# whenever the safety layer shuts the gate, ego stops, or the Orin does.
# legacy_uart_bridge (the Motor Pi) copies the counter into every serial frame (version 2)
# and never makes one up; the ESP32 brakes when it hasn't changed for 100 ms.

std_msgs/Header header   # the command's own header, passed on (ego's stamp)
uint8 counter            # +1 for each command passed on: 1, 2 ... 255, 0, 1 ...
