import os
from typing import Optional
from loguru import logger
import sys





def get_logger(
    name: Optional[str] = None,
    log_dir: Optional[str] = None,
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True,
    log_format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
) -> logger.__class__:
    """获取日志记录器

    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
        log_level: 日志级别 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
        console_output: 是否输出到控制台
        log_format: 日志格式 (loguru格式)

    Returns:
        logger: 配置好的loguru日志记录器
    """
    if name is None:
        name = "echoai"

    return setup_logger(
        name=name,
        log_dir=log_dir,
        log_level=log_level,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console_output=console_output,
        log_format=log_format
    )


def setup_logger(
    name: str,
    log_dir: Optional[str] = None,
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True,
    log_format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
) -> logger.__class__:
    """配置日志记录器

    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
        log_level: 日志级别 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
        console_output: 是否输出到控制台
        log_format: 日志格式 (loguru格式)

    Returns:
        logger: 配置好的loguru日志记录器
    """
    # 创建一个新的logger实例
    new_logger = logger.bind(name=name)
    
    # 移除默认的handler
    new_logger.remove()
    
    # 确定日志目录的绝对路径
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if log_dir is None:
        log_dir = os.path.join(project_root, "logs")
    elif not os.path.isabs(log_dir):
        log_dir = os.path.join(project_root, log_dir)

    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)

    # 添加控制台处理器
    if console_output:
        new_logger.add(
            sys.stdout,
            format=log_format,
            level=log_level,
            colorize=True
        )

    # 添加文件处理器
    log_file = os.path.join(log_dir, f"{name}.log")
    new_logger.add(
        log_file,
        format=log_format,
        level=log_level,
        rotation=max_bytes,
        retention=backup_count,
        encoding="utf-8"
    )

    # 添加错误日志文件处理器
    error_log_file = os.path.join(log_dir, f"{name}_error.log")
    new_logger.add(
        error_log_file,
        format=log_format,
        level="ERROR",
        rotation=max_bytes,
        retention=backup_count,
        encoding="utf-8"
    )

    return new_logger

