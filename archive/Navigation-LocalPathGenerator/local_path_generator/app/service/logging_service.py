import logging
import colorlog
import os
from datetime import datetime

class DailyFileHandler(logging.FileHandler):
    def __init__(self, log_dir="logs", encoding="utf-8"):
        self.log_dir = log_dir
        self.encoding = encoding
        self.current_date = None
        self.baseFilename = None
        self._update_log_file()
        super().__init__(self.baseFilename, encoding=encoding)

    def _update_log_file(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.current_date != today:
            self.current_date = today
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir, exist_ok=True)
            self.baseFilename = os.path.join(self.log_dir, f"{today}.log")

    def emit(self, record):
        self._update_log_file()
        if self.stream and self.stream.name != self.baseFilename:
            self.close()
            self.baseFilename = self.stream.name
            self.stream = self._open()
        super().emit(record)


def get_logger(log_dir: str = "logs"):
    console_handler = colorlog.StreamHandler()
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red"
        }
    )
    console_handler.setFormatter(console_formatter)

    file_handler = DailyFileHandler(log_dir=log_dir, encoding="utf-8")
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    logger = logging.getLogger()

    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger