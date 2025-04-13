import asyncio

from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse

from echoai.server.models.chat import ChatChunkResponse, ChatRequest, ChatResponse

app = FastAPI()

@app.route("/sse/{request_id}", methods=["GET"])
async def sse_endpoint(request: Request, request_id: str):
    ...