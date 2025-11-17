from loguru import logger
from pathlib import Path


def configure_logging() -> None:
    """配置日志记录器"""
    dirpath = Path("logs")

    # 确保日志目录存在
    dirpath.mkdir(parents=True, exist_ok=True)

    # 移除默认的控制台输出
    logger.remove()
    
    # 只添加文件输出
    logger.add(
        dirpath / "eflycode.log",
        rotation="10 MB",
        retention="1 week",
        encoding="utf-8",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

    # 专门记录 ERROR 的日志，追踪调用栈
    logger.add(
        dirpath / "error.log",
        rotation="10 MB",
        retention="1 week",
        encoding="utf-8",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        backtrace=True
    )

    logger.debug(f"日志记录器已配置，日志文件路径: {dirpath / 'eflycode.log'}")

configure_logging()