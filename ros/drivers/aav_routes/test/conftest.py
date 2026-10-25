"""The tests import this package, and aav_hud's route.py, from the source tree."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[2]
for path in (HERE.parent, SRC / 'hud' / 'aav_hud'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
