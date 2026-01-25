import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def get_logger(log_path = "logs/smm_planner.log") -> logging.Logger:
    logger = logging.getLogger("smm_planner")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger.addHandler(handler)
    logger.addHandler(console)
    return logger
