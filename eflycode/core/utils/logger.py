from concurrent.futures import thread
from mimetypes import init
import os
from pathlib import Path
from typing import Optional, Union
from loguru import logger as _logger


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
_DEFAULT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "{process.name}:{process.id} | {thread.name}:{thread.id} | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

def init_logger(
    *,
    level: Optional[str] = None,
    log_dir: Optional[Union[str, Path]],
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

    level = (level or _env_str("EFLYCODE_LOG_LEVEL", "INFO"))
    log_dir = (log_dir or _env_str("EFLYCODE_LOG_DIR", ".eflycode/logs"))
    log_file = (log_file or _env_str("EFLYCODE_LOG_FILE", "eflycode.log"))
    log_dirpath = Path(log_dir).expanduser().resolve()

    rotation = (rotation or _env_str("EFLYCODE_LOG_ROTATION", "10 MB"))
    retention = (retention or _env_str("EFLYCODE_LOG_RETENTION", "14 days"))
    compression = (compression or _env_str("EFLYCODE_LOG_COMPRESSION", "tar.gz"))

    enqueue = (enqueue or _env_bool("EFLYCODE_LOG_ENQUEUE", True))
    backtrace = (backtrace or _env_bool("EFLYCODE_LOG_BACKTRACE", True))
    diagnose = (diagnose or _env_bool("EFLYCODE_LOG_DIAGNOSE", True))
    serialize = (serialize or _env_bool("EFLYCODE_LOG_SERIALIZE", True))
    
    fmt = fmt or _DEFAULT_FORMAT

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
        encoding="utf-8",
    )

    _LOGGER_CONFIGURED = True

# 绑定 logger 的 name 为 "eflycode"
logger = _logger.bind(name="eflycode")

init_logger()