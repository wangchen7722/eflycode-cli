from loguru import logger

from echo.schema.config import LoggingConfig

def configure_logging(logging_config: LoggingConfig) -> None:
    """配置日志记录器"""
    logger.add(
        logging_config.dirpath / logging_config.filename,
        rotation=logging_config.rotation,
        retention=logging_config.retention,
        encoding=logging_config.encoding,
        level=logging_config.level,
        format=logging_config.format
    )
    # 专门记录 ERROR 的日志，追踪调用栈
    logger.add(
        logging_config.dirpath / "error.log",
        rotation=logging_config.rotation,
        retention=logging_config.retention,
        encoding=logging_config.encoding,
        level="ERROR",
        format=logging_config.format,
        backtrace=True
    )
    logger.error(f"日志记录器已配置，日志文件路径: {logging_config.dirpath / logging_config.filename}")
