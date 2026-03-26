# utils/logger.py
import logging
import os
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console

console = Console()

def setup_logger(name: str) -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/{name}_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # Rich console handler — pretty colors in terminal
        rich_handler = RichHandler(console=console, rich_tracebacks=True, markup=True)
        rich_handler.setLevel(logging.INFO)
        logger.addHandler(rich_handler)

        # File handler — full debug log saved to disk
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        ))
        logger.addHandler(file_handler)

    return logger