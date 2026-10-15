"""The tests import this package, and aav_scripted's speed profile, from the source tree."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
for path in (HERE.parent, HERE.parent.parent / 'aav_scripted'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
