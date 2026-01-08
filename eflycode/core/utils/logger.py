import os
from pathlib import Path
from typing import Optional, Union

from loguru import logger as _logger

from eflycode.core.constants import (
    LOG_LEVEL,
    LOG_DIR,
    LOG_FILE,
    LOG_ROTATION,
    LOG_RETENTION,
    LOG_COMPRESSION,
    LOG_ENCODING,
    LOG_FORMAT,
    EFLYCODE_DIR,
)


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}

def _env_str(name: str, default: str) -> str:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().upper()

_LOGGER_CONFIGURED = False

def init_logger(
    *,
    level: Optional[str] = None,
    log_dir: Optional[Union[str, Path]] = None,
    log_file: Optional[str] = None,
    rotation: Optional[str] = None,
    retention: Optional[str] = None,
    compression: Optional[str] = None,
    enqueue: Optional[bool] = None,
    backtrace: Optional[bool] = None,
    diagnose: Optional[bool] = None,
    serialize: Optional[bool] = None,
    fmt: Optional[str] = None,
    force: Optional[str] = None,
) -> None:
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED and not force:
        print("logger already configured, skipping...")
        return

    level = (level or _env_str("EFLYCODE_LOG_LEVEL", LOG_LEVEL))
    log_dir = (log_dir or _env_str("EFLYCODE_LOG_DIR", f"{EFLYCODE_DIR}/{LOG_DIR}"))
    log_file = (log_file or _env_str("EFLYCODE_LOG_FILE", LOG_FILE))
    log_dirpath = Path(log_dir).expanduser().resolve()

    rotation = (rotation or _env_str("EFLYCODE_LOG_ROTATION", LOG_ROTATION))
    retention = (retention or _env_str("EFLYCODE_LOG_RETENTION", LOG_RETENTION))
    compression = (compression or _env_str("EFLYCODE_LOG_COMPRESSION", LOG_COMPRESSION))

    enqueue = (enqueue or _env_bool("EFLYCODE_LOG_ENQUEUE", True))
    backtrace = (backtrace or _env_bool("EFLYCODE_LOG_BACKTRACE", True))
    diagnose = (diagnose or _env_bool("EFLYCODE_LOG_DIAGNOSE", True))
    serialize = (serialize if serialize is not None else _env_bool("EFLYCODE_LOG_SERIALIZE", False))
    
    fmt = fmt or LOG_FORMAT

    _logger.remove()
    log_dirpath.mkdir(parents=True, exist_ok=True)
    log_filepath = log_dirpath / log_file
    _logger.add(
        log_filepath,
        level=level,
        format=fmt,
        rotation=rotation,
        retention=retention,
        compression=compression,
        backtrace=backtrace,
        diagnose=diagnose,
        enqueue=enqueue,
        serialize=serialize,
        encoding=LOG_ENCODING,
    )

    _LOGGER_CONFIGURED = True

# 绑定 logger 的 name 为 "eflycode"
logger = _logger.bind(name="eflycode")

init_logger()
