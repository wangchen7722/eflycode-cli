import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict
from threading import Lock

# 用于存储已创建的logger实例
_logger_cache: Dict[str, logging.Logger] = {}

class ThreadSafeRotatingFileHandler(RotatingFileHandler):
    """线程安全的日志文件处理器"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = Lock()

    def emit(self, record):
        with self._lock:
            super().emit(record)

def get_logger(
    name: str,
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
) -> logging.Logger:
    """获取日志记录器

    如果指定名称的logger已存在，则直接返回缓存的实例；
    否则创建一个新的logger实例并缓存它。

    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
        log_level: 日志级别
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
        console_output: 是否输出到控制台
        log_format: 日志格式

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    if name in _logger_cache:
        return _logger_cache[name]
    
    logger = setup_logger(
        name=name,
        log_dir=log_dir,
        log_level=log_level,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console_output=console_output,
        log_format=log_format
    )
    _logger_cache[name] = logger
    return logger

def setup_logger(
    name: str,
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
) -> logging.Logger:
    """配置日志记录器

    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
        log_level: 日志级别
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
        console_output: 是否输出到控制台
        log_format: 日志格式

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 清除现有的处理器
    if logger.handlers:
        logger.handlers.clear()

    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)

    # 创建格式化器
    formatter = logging.Formatter(log_format)

    # 添加文件处理器
    log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = ThreadSafeRotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 添加错误日志文件处理器
    error_log_file = os.path.join(log_dir, f"{name}_error.log")
    error_file_handler = ThreadSafeRotatingFileHandler(
        error_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    logger.addHandler(error_file_handler)

    # 添加控制台处理器
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger