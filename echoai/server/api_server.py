import asyncio
import json
import traceback
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import StreamingResponse

from echoai.server.handlers.exception_handler import (
    request_validation_exception_handler,
    service_exception_handler,
)
from echoai.server.models.chat import ChatChunkResponse, ChatRequest, ChatResponse
from echoai.server.models.exception import ServiceException
from echoai.server.models.response import result_response, ServerSentEvent
from echoai.server.utils.validator import validate_uuid4
from echoai.utils.logger import get_logger

app = FastAPI()
app.add_exception_handler(ServiceException, service_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

logger = get_logger()

mq: Dict[str, asyncio.Queue] = {}

@app.get("/sse/{request_id}")
async def sse_endpoint(request: Request, request_id: str):
    if not validate_uuid4(request_id):
        raise ServiceException(code=400, message="非法的请求")

    if request_id not in mq:
        mq[request_id] = asyncio.Queue()

    async def event_generator():
        while True:
            try:
                # 1. 检查客户端是否断开连接
                is_disconnected = await request.is_disconnected()
                if is_disconnected:
                    break
                # 2. 从队列中获取消息, 超时则发送一个心跳包
                try:
                    message = await asyncio.wait_for(mq[request_id].get(), timeout=10)
                except asyncio.TimeoutError:
                    message = None
                if message is None:
                    data = {"type": "ping"}
                else:
                    data = {"type": "message", "message": message}
                # 3. 发送消息到客户端
                yield ServerSentEvent(event="message", data=json.dumps(data))
                # 4. 检查当前 request 任务是否完成
                if message and message == "[DONE]":
                    break
            except Exception as e:
                error_details = traceback.format_exc()
                logger.error(f"Error in sse_endpoint: {error_details}")
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/agent/chat")
@result_response
async def agent_chat(chat_request: ChatRequest):
    request_id = chat_request.request_id
    if request_id not in mq:
        raise ServiceException(code=400, message="非法的请求")
    print(chat_request)
    async def push_messages():
        try:
            # 模拟延时处理，并分多次推送消息块
            await asyncio.sleep(1)
            await mq[request_id].put("这是第1个消息分块。")
            await asyncio.sleep(1)
            await mq[request_id].put("这是第2个消息分块。")
            await asyncio.sleep(1)
            await mq[request_id].put("这是第3个消息分块。")
            await asyncio.sleep(1)
            # 最后推送一个标识结束的消息，如 "DONE"
            await mq[request_id].put("[DONE]")
        except Exception as e:
            print(f"推送消息到 MQ 时异常: {e}")
    asyncio.create_task(push_messages())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8088)