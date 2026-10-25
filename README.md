# ecolo-av

Single code base for the Ecolo autonomous vehicle (SYSC 4907, Carleton University).
Goal for Gate 4 (26 Feb 2027): drive from GPS point A to B at 1 m/s and stop within 1 m.

**New here? Start with [docs/getting-started.md](docs/getting-started.md).**

## Layout

| Folder | What it holds |
|---|---|
| `ros/` | Every ROS 2 package, one folder per layer (proposal section 3.1) |
| `firmware/` | Rust firmware for the ESP32 spine. Built by Cargo, not colcon |
| `tests/` | Tests that span packages |
| `tools/` | Scripts |
| `docs/` | Starting guide, interface contract, decision log |
| `archive/` | The 27 earlier repositories, with history. Read and port from here |

## Common commands

    pixi install          set up the environment
    pixi run turtlesim    start TurtleSim
    pixi run teleop       drive it from the keyboard (second terminal)
    pixi run test         run every test CI runs
