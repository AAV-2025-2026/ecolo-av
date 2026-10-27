# One actuator: what it was told, and what it did. For plotting command against measured
# (Foxglove, PlotJuggler) and for the actuator tests (docs/tests.md, stage 4).
#
# Published by the backend on /vehicle/steering (rad, positive = left, the virtual centre
# wheel), /vehicle/throttle (0..1 of full throttle) and /vehicle/brake (0..1 of full
# brake). NaN means not known: the spine decides throttle and brake itself, so their
# command side is NaN on the car and the bench.

std_msgs/Header header
float32 command     # what was asked for
float32 measured    # what the actuator did (in a simulator: what its model did)
