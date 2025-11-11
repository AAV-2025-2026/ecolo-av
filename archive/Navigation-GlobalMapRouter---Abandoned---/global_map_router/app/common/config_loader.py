import os, sys
from pathlib import Path
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

GOOGLE_MAP_API_KEY = os.getenv("GOOGLE_MAP_API_KEY")

CUR_POS_LAT_TEST = float(os.getenv("CUR_POS_LAT_TEST","0"))
CUR_POS_LON_TEST = float(os.getenv("CUR_POS_LON_TEST","0"))

#SAMPLE_CONST = os.getenv("SAMPLE_CONST")
