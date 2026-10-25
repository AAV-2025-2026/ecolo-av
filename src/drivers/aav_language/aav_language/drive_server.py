"""
The DRIVE tool server: MCP over stdio, so a language model (or any AI app) can drive.

Separate from the read-only server (tools/mcp_server.py), on purpose: this one moves the
car. High-level tools only, never raw velocities:

  status()                                   speed, pose, GPS, e-stop, armed, who drives
  drive(distance_m, speed_mps, direction, curvature, wait)
  turn(angle_deg, radius_m, direction, speed_mps, wait)
  stop()          estop()          go_to_gps(lat, lon, wait)          wait(seconds)
  check(tool, arguments)          would that call be refused? (for the agent's plan)

Every rule is checked here, not by the model: drive_tools.py and safety.py. Its ROS node
is language_drive (ros_backend.py, which lists the topics and actions). When the app that
started it goes away (stdin closes), it cancels any drive still running.

    pixi run -e mcp drive-server            turtle, sim or bench (this computer only)
    pixi run -e mcp drive-server --car      the real car: only with a safety driver
    python3 -m aav_language.drive_server --fake     no ROS at all: a pretend car

Without --car it refuses to drive unless ROS discovery stays on this computer
(ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST, which tools/ros.sh --local sets) or a simulator
publishes /clock, and none of the car's hardware nodes is in sight.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
from typing import Optional

from aav_language import safety
from aav_language.drive_tools import default_log_path, DriveTools

INSTRUCTIONS = """\
Drives the Carleton AAV (or its stand-in: turtlesim, Gazebo, bench mode) with high-level
moves. Distances are in metres, speeds in m/s, angles in degrees (+ = left). drive()
covers the whole distance, speeding up and slowing down included. The server enforces
hard limits and refuses anything above them; it never clears an e-stop. A person on the
joystick or keyboard always overrides it."""


def build_server(tools: DriveTools):
    """Make the MCP server, with one tool per DriveTools method."""
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations

    server = MCPServer('aav-drive', title='AAV drive (moves the car)',
                       instructions=INSTRUCTIONS)
    moves = ToolAnnotations(read_only_hint=False, destructive_hint=True,
                            idempotent_hint=False, open_world_hint=True)
    reads = ToolAnnotations(read_only_hint=True, open_world_hint=True)

    def out(result) -> str:
        return json.dumps(result)

    @server.tool(annotations=reads, structured_output=False)
    def status() -> str:
        """
        Tell where the car is and what it is doing.

        Speed, pose, GPS fix, e-stop, armed, which driver the mux passes on, any drive
        running, and the limits.
        """
        return out(tools.status())

    @server.tool(annotations=moves, structured_output=False)
    def drive(distance_m: float, speed_mps: float = 0.5, direction: str = 'forward',
              curvature: float = 0.0, wait: bool = True) -> str:
        """
        Drive a distance in metres, in total (speeding up and slowing down included).

        direction is "forward" or "reverse". speed_mps is the top speed (default 0.5).
        curvature in 1/m, + = left, 0 = straight. Returns when the car has stopped.
        """
        return out(tools.drive(distance_m, speed_mps, direction, curvature, wait))

    @server.tool(annotations=moves, structured_output=False)
    def turn(angle_deg: float, radius_m: float, direction: str, speed_mps: float = 0.5,
             wait: bool = True) -> str:
        """
        Turn while driving forward, along an arc.

        direction is "left" or "right"; angle_deg is how far, in degrees (90 = a quarter
        turn); radius_m is the circle's radius in metres. Returns when the car has stopped.
        """
        return out(tools.turn(angle_deg, radius_m, direction, speed_mps, wait))

    @server.tool(annotations=moves, structured_output=False)
    def go_to_gps(lat: float, lon: float, wait: bool = True) -> str:
        """Drive to a latitude/longitude with Nav2 (only when Nav2 is running)."""
        return out(tools.go_to_gps(lat, lon, wait))

    @server.tool(annotations=moves, structured_output=False)
    def stop() -> str:
        """Stop: cancel the running drive; the car slows down to a stop."""
        return out(tools.stop())

    @server.tool(annotations=moves, structured_output=False)
    def estop() -> str:
        """Emergency stop: block every driver until a person clears it."""
        return out(tools.estop())

    @server.tool(annotations=reads, structured_output=False)
    def wait(seconds: float) -> str:
        """Wait a number of seconds (up to 120), doing nothing."""
        return out(tools.wait(seconds))

    @server.tool(annotations=reads, structured_output=False)
    def check(tool: str, arguments: dict) -> str:
        """
        Check whether a drive, turn or go_to_gps call would be refused now.

        Moves nothing. Returns {"ok": true} or {"ok": false, "message": why}.
        """
        why = tools.check(tool, arguments)
        return out({'ok': why is None, 'message': why or 'allowed'})

    return server


def make_tools(args, log) -> DriveTools:
    caps = safety.Caps(max_speed=args.max_speed)
    if args.fake:
        from aav_language.fake_backend import FakeBackend
        backend = FakeBackend()
        log_path = None
    else:
        from aav_language.ros_backend import RosBackend
        backend = RosBackend()
        log_path = default_log_path()
    return DriveTools(backend, car=args.car, caps=caps, log=log, log_path=log_path)


def parse_args(argv: Optional[list] = None):
    p = argparse.ArgumentParser(description='The AAV drive tool server (MCP over stdio).')
    p.add_argument('--car', action='store_true',
                   help='allow driving the REAL car (only with a safety driver on board)')
    p.add_argument('--max-speed', type=float, default=1.0,
                   help="the server's speed cap, m/s (ego's max_speed caps it too)")
    p.add_argument('--fake', action='store_true', help='a pretend car: no ROS at all')
    return p.parse_args(argv)


def main(argv: Optional[list] = None):
    args = parse_args(argv)

    def log(line: str):
        # stdout carries MCP: the log goes to stderr.
        print(f'[drive-server] {line}', file=sys.stderr, flush=True)

    if args.max_speed > 2.0:
        sys.exit('--max-speed above 2 m/s is not allowed')
    if not sys.stdin.isatty():
        # Started by an app (the agent, Claude...): Ctrl-C in the app's terminal reaches
        # this process too, and it must live to send the stop() the app asks for. The app
        # ends it by closing stdin.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    tools = make_tools(args, log)
    log(f'started: car={args.car} fake={args.fake} cap={args.max_speed} m/s')
    try:
        build_server(tools).run()
    finally:
        # The app has gone (or the server failed): never leave a drive running unattended.
        cancelled = tools.backend.cancel_all()
        if cancelled:
            log(f'the app went away: cancelled {cancelled}, slowing to a stop')


if __name__ == '__main__':
    main()
