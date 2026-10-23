# The sensor mux's verdict, twice a second on /system/sensor_mux/state: does every sensor
# come from the one source this run asked for (source:=real, sim, bench or replay)?
#
# The output mux reads it: the real car's commands flow only while it says ok for REAL,
# and keeps saying so (a silent sensor mux stops the car too).

std_msgs/Header header
uint8 source              # what source:= asked for: a SensorSource value (REAL, SIM...)
bool ok                   # every sensor and every announcement agrees with it
string[] problems         # one line each, for people: empty when ok
SensorSource[] sensors    # each sensor that publishes, and the source it was found to be
