#!/usr/bin/env python3
"""
Compare the running ROS graph with docs/interfaces.yaml. Needs a sourced Jazzy install.

usage: tools/check_graph.py --profile turtle|sim|car [--wait 5]

Reports, for every topic in the contract:
  FAIL  a topic marked live in this profile has no publisher, or a type differs
  ok    present with the right type (and who publishes/subscribes)
  -     not running (fine if it isn't live in this profile)
and lists topics that are running but not in the contract (a typo, or the contract
needs an entry). Exit status 1 if anything failed: usable in a test script.
"""

import argparse
from pathlib import Path
import sys
import time

import rclpy
import yaml

ROOT = Path(__file__).resolve().parents[1]
# Every ROS system has these. /diagnostics and the */set_pose topics come with
# robot_localization (the contract lists its set_pose services instead).
IGNORE = {'/parameter_events', '/rosout', '/diagnostics',
          '/ekf_local/set_pose', '/ekf_global/set_pose'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', required=True, choices=['turtle', 'sim', 'car'])
    ap.add_argument('--wait', type=float, default=3.0, help='seconds to let discovery settle')
    ap.add_argument('--spec', default=str(ROOT / 'docs' / 'interfaces.yaml'))
    args = ap.parse_args()
    spec = yaml.safe_load(Path(args.spec).read_text())

    rclpy.init()
    node = rclpy.create_node('check_graph')
    time.sleep(args.wait)
    running = dict(node.get_topic_names_and_types())
    failed = 0
    for name, t in spec['topics'].items():
        live = args.profile in t.get('live', [])
        pubs = sorted({p.node_name for p in node.get_publishers_info_by_topic(name)})
        subs = sorted({s.node_name for s in node.get_subscriptions_info_by_topic(name)}
                      - {'check_graph'})
        types = running.get(name, [])
        if types and t['type'] not in types:
            print(f'FAIL  {name}: type {types}, contract says {t["type"]}')
            failed += 1
        elif live and not pubs:
            print(f'FAIL  {name}: no publisher (must be live in {args.profile})')
            failed += 1
        elif pubs or subs:
            print(f'ok    {name}  pub {pubs or "-"}  sub {subs or "-"}')
        else:
            print(f'-     {name}')
    extra = sorted(set(running) - set(spec['topics']) - IGNORE)
    # Costmap internals, the topics ROS makes inside every action, and turtlesim's own.
    internal = ('/local_costmap/', '/global_costmap/', '/turtle1/')
    extra = [n for n in extra if not n.startswith(internal) and '/_action/' not in n]
    if extra:
        print('\nRunning but not in docs/interfaces.yaml:')
        for n in extra:
            print(f'  {n}  {running[n]}')
    node.destroy_node()
    rclpy.shutdown()
    print(f'\n{failed} failed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
