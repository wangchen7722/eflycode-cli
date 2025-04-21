import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import json
import sys
import traceback
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from loguru import logger
from redis.asyncio import Redis
from starlette.responses import StreamingResponse

from echoai.cli.utils.logger import get_logger
from echoai.server.constants import CHAT_PENDING_TTL, REDIS_URL, CHAT_PENDING_REDIS_KEY
from echoai.server.handlers.exception_handler import (
    request_validation_exception_handler,
    service_exception_handler,
)
from echoai.server.models.chat import ChatChunkResponse, ChatRequest, ChatResponse
from echoai.server.models.exception import ServiceException
from echoai.server.models.response import ServerSentEvent, result_response
from echoai.server.utils.snowflake import Snowflake
from echoai.server.utils.validator import validate_uuid4

logger.remove()
logfile = f"logs/{datetime.strftime(datetime.now(), '%Y-%m-%d')}.log"
logger.add(
    logfile,
    rotation="10 MB",
    retention="14 days",
    compression="zip",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)
logger.add(
    sys.stdout,
    level="DEBUG",
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
)

redis = Redis.from_url(REDIS_URL, decode_responses=True)
snowflake = Snowflake(datacenter_id=1, worker_id=1)

async def redis_pending_gc():
    """Garbage Collection for Redis Pending Requests
    定期清理 Redis 中过期的 Pending 请求
    """
    while True:
        ids = await redis.hkeys(CHAT_PENDING_REDIS_KEY)
        

@asynccontextmanager
async def lifespan(app: FastAPI):
    # asyncio.create_task()
    ...

app = FastAPI()
app.add_exception_handler(ServiceException, service_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

# @app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)