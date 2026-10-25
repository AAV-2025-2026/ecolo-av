"""The output mux's heartbeat counter (TODO 50)."""

from aav_io_mux.heartbeat import Counter, heartbeat_topic


def test_it_counts_each_command_and_wraps_in_a_byte():
    c = Counter()
    beats = [c.beat() for _ in range(300)]
    assert beats[:3] == [1, 2, 3]
    assert beats[254:257] == [255, 0, 1]
    assert all(0 <= b <= 255 for b in beats)
    # Every beat differs from the one before: that change is what the ESP32 looks for.
    assert all(a != b for a, b in zip(beats, beats[1:]))


def test_it_never_moves_by_itself():
    c = Counter()
    c.beat()
    assert c.value == 1
    assert c.value == 1


def test_the_topic_sits_beside_the_command():
    assert heartbeat_topic('car') == '/control/car/heartbeat'
