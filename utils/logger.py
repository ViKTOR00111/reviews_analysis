import os
import sys
from datetime import timedelta
from loguru import logger
from loguru._defaults import LOGURU_TRACE_NO


def setup_logger(settings):
    file_path = "/".join(settings.LOG_FILEPATH.split("/")[:-1])

    try:
        os.makedirs(file_path, exist_ok=True)
    except FileNotFoundError:
        pass  # if passed file path consist only of filename

    logger.remove()
    log_format = "[{time:YYYY-MM-DD HH:mm:ss ZZ}] [{process}] [{level}] [{name}] {message}"

    logger.add(
        sink=sys.stdout,
        level=LOGURU_TRACE_NO,
        format=log_format
    )
    logger.add(
        sink=settings.LOG_FILEPATH,
        level=LOGURU_TRACE_NO,
        format=log_format,
        rotation=timedelta(days=settings.LOG_ROTATION),
        retention=timedelta(days=settings.LOG_RETENTION)
    )
