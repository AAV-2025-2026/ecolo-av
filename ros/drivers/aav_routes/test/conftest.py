"""The tests import this package from the source tree."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
