import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
APPWORLD_ROOT = os.environ.get("APPWORLD_ROOT", str(DATA / "native/appworld"))
APPWORLD_PYTHON = os.environ.get("EA_APPWORLD_PYTHON", sys.executable)
