from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from echoai.server.models.exception import ServiceException
from echoai.server.models.response import ResultResponse


async def service_exception_handler(request: Request, exception: ServiceException):
    """
    服务异常处理程序。
    """
    # TODO: 添加日志记录等等
    error_response = ResultResponse.error(exception.code, exception.message)
    return JSONResponse(content=error_response.model_dump(exclude_none=True))

async def request_validation_exception_handler(request: Request, exception: RequestValidationError):
    """
    Pydantic V2 请求验证异常处理程序。
    """
    # TODO: 添加日志记录等等
    error_details = exception.errors()
    error_response = ResultResponse.error(400, "请求数据校验错误")
    return JSONResponse(content=error_response.model_dump(exclude_none=True))