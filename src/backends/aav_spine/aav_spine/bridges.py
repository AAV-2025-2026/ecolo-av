"""
Which spine_bridge the launch files start: the Rust one or this package's Python one.

No ROS imports. Both are the same node, `spine_bridge`, on the same topics, with this
package's config/spine.yaml: aav_spine_bridge (Rust, T1.8) and aav_spine (Python, kept
until the Rust one has run on the car). The launch argument is `bridge:=rust|python`, in
spine.launch.py, bench.launch.py, sim.launch.py and gazebo.launch.py.
"""

PACKAGES = {'rust': 'aav_spine_bridge', 'python': 'aav_spine'}
DEFAULT = 'rust'
EXECUTABLE = 'spine_bridge'


def package(language: str) -> str:
    """Return the ROS package whose spine_bridge to start, for bridge:=<language>."""
    try:
        return PACKAGES[language.strip().lower()]
    except KeyError:
        raise ValueError(f'bridge:={language}: use one of {sorted(PACKAGES)}') from None
