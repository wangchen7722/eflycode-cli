import asyncio
import json
import sys
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from loguru import logger
from redis.asyncio import Redis
from starlette.responses import StreamingResponse

from echoai.cli.utils.logger import get_logger
from echoai.server.constants import (
    REDIS_CHAT_CANCEL_KEY,
    REDIS_CHAT_PENDING_KEY,
    REDIS_CHAT_PENDING_TTL,
    REDIS_URL,
)
from echoai.server.handler.exception_handler import (
    request_validation_exception_handler,
    service_exception_handler,
)
from echoai.server.model.chat import ChatChunkResponse, ChatRequest, ChatResponse
from echoai.server.model.exception import ServiceException
from echoai.server.model.response import ServerSentEvent, result_response
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

async def redis_chat_pending_gc():
    """Garbage Collection for Redis Pending Chat Requests
    定期清理 Redis 中过期的 Pending 请求
    """
    while True:
        now = int(time.time())
        pending_items = await redis.hgetall(REDIS_CHAT_PENDING_TTL)
        if pending_items:
            pipe = redis.pipeline()
            for mid, deadline in pending_items.items():
                if int(deadline) < now:
                    # 标记为已取消
                    pipe.hdel(REDIS_CHAT_PENDING_TTL, mid)
                    pipe.hset(REDIS_CHAT_CANCEL_KEY, mid, 1)
            await pipe.execute()
            logger.debug(f"[Redis] 清理过期的 Pending 请求: {mid}")
        await asyncio.sleep(3)
        

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行 Redis Chat Request 清理
    asyncio.create_task(
        redis_chat_pending_gc(),
    )

app = FastAPI()
app.add_exception_handler(ServiceException, service_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)