import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, Union


def retry(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retry_exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    should_retry: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
):
    """重试装饰器
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试延迟时间（秒）
        retry_exceptions: 需要重试的异常类型
        should_retry: 自定义重试判断函数，接收异常对象作为参数，返回是否需要重试
        on_retry: 重试回调函数，在每次重试前调用，接收当前重试次数、异常对象和延迟时间作为参数
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    # 判断是否需要重试
                    if should_retry and not should_retry(e):
                        raise
                    
                    # 最后一次重试失败，直接抛出异常
                    if attempt == max_retries - 1:
                        raise
                    
                    # 计算延迟时间
                    delay = retry_delay * (attempt + 1)
                    
                    # 调用重试回调函数
                    if on_retry:
                        on_retry(attempt + 1, e, delay)
                    
                    # 延迟重试
                    time.sleep(delay)
        return wrapper
    return decorator