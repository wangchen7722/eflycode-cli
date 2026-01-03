from __future__ import annotations

import threading
import time
from typing import List

from eflycode.ui.event import UIEventType, AgentUIEventType
from eflycode.util.event_bus import EventBus
from eflycode.util.logger import logger


class MockAgentRunner:
    """
    简单的 Agent 模拟器：监听用户输入并以流式形式输出响应。
    """

    def __init__(self, event_bus: EventBus, stream_interval: float = 0.35) -> None:
        self._event_bus = event_bus
        self._stream_interval = stream_interval
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

        self._event_bus.subscribe(UIEventType.USER_INPUT_RECEIVED, self._handle_user_input)
        self._event_bus.subscribe(UIEventType.INTERRUPT, self._handle_interrupt)

    def _handle_user_input(self, event: str, data: dict) -> None:
        text = (data or {}).get("text", "").strip()
        if not text:
            return

        with self._lock:
            if self._worker and self._worker.is_alive():
                logger.warning("已有任务在执行，忽略新输入。")
                self._event_bus.emit(
                    UIEventType.WARNING,
                    {"message": "已有任务正在生成内容，请先等待完成或按 Ctrl+C 中断。"},
                )
                return

            self._cancel_event.clear()
            self._worker = threading.Thread(
                target=self._simulate_agent,
                args=(text,),
                daemon=True,
                name="mock-agent-runner",
            )
            self._worker.start()

    def _handle_interrupt(self, event: str, data: dict) -> None:
        if self._worker and self._worker.is_alive():
            logger.info("收到中断请求，正在停止模拟 agent。")
            self._cancel_event.set()

    def _simulate_agent(self, prompt: str) -> None:
        intro = f"收到用户输入：{prompt}\n"
        self._event_bus.emit(
            AgentUIEventType.THINK_START,
            {"title": "Mock Agent", "content": intro},
        )

        stream_chunks = self._build_stream_segments(prompt)
        buffer: List[str] = []

        for chunk in stream_chunks:
            if self._cancel_event.is_set():
                self._event_bus.emit(
                    AgentUIEventType.THINK_END,
                    {"notice": "生成已中断。"},
                )
                self._event_bus.emit(
                    UIEventType.WARNING,
                    {"message": "已中断当前响应。"},
                )
                return

            buffer.append(chunk)
            self._event_bus.emit(AgentUIEventType.THINK_UPDATE, {"content": chunk})
            time.sleep(self._stream_interval)

        result = "".join(buffer)

        self._event_bus.emit(
            AgentUIEventType.THINK_END,
            {"notice": "生成完成。"},
        )
        self._event_bus.emit(
            AgentUIEventType.MESSAGE_UPDATE,
            {"text": f"\nAssistant:\n{result}\n"},
        )
        self._event_bus.emit(AgentUIEventType.MESSAGE_END, {})

    @staticmethod
    def _build_stream_segments(prompt: str) -> List[str]:
        base = [
            "正在分析需求...",
            "确定关键意图...",
            "构造解决步骤...",
            "生成示例代码...",
            "检查潜在风险...",
            "总结建议。",
        ]

        segments: List[str] = []
        for sentence in base:
            segments.append(f"{sentence}\n")

        segments.append(f"\n最终回答：针对「{prompt}」可以按上述步骤完成。\n")
        return segments

