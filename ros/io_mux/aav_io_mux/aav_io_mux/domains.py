"""
A ROS domain nobody else on this computer is using, for a test or a check.

The guard test (test_real_backend_guard.py), sim_check.py and bench_check.py each run a
whole graph on a private domain, picked from 150-230. Picked at random, two runs can land
on one domain and see each other: on 24 Oct a guard test's REAL spine_bridge latched a
Gazebo check's output mux (domain 193). free_domain looks first: a domain counts as free
when a probe node there sees no other node and no topic but ROS's own for `look` s.

Discovery stays on this computer (ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST), as in the
runs that use it. Two runs probing the same empty domain at the same moment can still
both pick it; the random order makes that rare.
"""

import os
import random
import time

import rclpy

# ROS's own topics: every domain with a node has them.
QUIET_TOPICS = {'/rosout', '/parameter_events'}


def in_use(domain: int, look: float = 1.5) -> list:
    """Return what a probe node on `domain` sees in `look` s: other nodes and topics."""
    context = rclpy.Context()
    rclpy.init(context=context, domain_id=domain)
    try:
        probe = rclpy.create_node('domain_probe', context=context)
        time.sleep(look)
        found = [n for n, _ in probe.get_node_names_and_namespaces() if n != 'domain_probe']
        found += sorted({t for t, _ in probe.get_topic_names_and_types()} - QUIET_TOPICS)
        probe.destroy_node()
        return found
    finally:
        rclpy.shutdown(context=context)


def free_domain(low: int = 150, high: int = 230, look: float = 1.5) -> int:
    """Return a domain from low to high that nobody on this computer uses now."""
    os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] = 'LOCALHOST'
    for domain in random.sample(range(low, high + 1), high - low + 1):
        if not in_use(domain, look):
            return domain
    raise RuntimeError(f'every ROS domain from {low} to {high} is in use on this computer')
