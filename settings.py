from crud import get_settings
from utils.db import init_db

try:
    settings = get_settings()
except:
    init_db()
    settings = get_settings()