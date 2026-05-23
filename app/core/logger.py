import logging
from pythonjsonlogger import jsonlogger


def setup_logger(name: str = "trading_system") -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
