import os
from loguru import logger


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