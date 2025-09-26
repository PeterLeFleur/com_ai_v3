"""
COM-AI v3 - Logging Configuration
Standardized logging setup for the entire application
"""

import logging
import sys
import os

def setup_logging(level: str | None = None):
    if level is None:
        from src.utils.config import get_settings
        settings = get_settings()
        level = settings.log_level

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    os.makedirs('logs', exist_ok=True)

    # Build handlers explicitly to control encodings
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    fileh = logging.FileHandler('logs/com_ai_v3.log', mode='a', encoding='utf-8')
    fileh.setLevel(numeric_level)
    fileh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    root = logging.getLogger()
    root.handlers = []              # reset any previous handlers (e.g., from basicConfig)
    root.setLevel(numeric_level)
    root.addHandler(console)
    root.addHandler(fileh)

    logging.getLogger('uvicorn').setLevel(logging.INFO)
    logging.getLogger('fastapi').setLevel(logging.INFO)
    logging.getLogger('src.brain').setLevel(logging.DEBUG)

    # (Use ASCII text here or ensure console supports UTF-8, which we set in the .bat)
    logging.getLogger(__name__).info(f"Logging configured - Level: {level}")
