import asyncio
import sys
from dataclasses import dataclass
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.application.current import get_app_or_none
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style


@dataclass
class UIState:
    streaming: bool = False                 # Agent 是否正在输出
    pending_line: Optional[str] = None      # 贴在输入框上方的一行（例如：刚刚发送的用户输入）
    queued: int = 0                         # 排队消息数量（可选）


state = UIState()
outbox: asyncio.Queue[str] = asyncio.Queue()


def invalidate():
    """让 prompt 立即重绘，从而更新 prompt 样式/提示行。"""
    app = get_app_or_none()
    if app:
        app.invalidate()


def prompt_message():
    """
    关键点：返回“多行 prompt”：
      第一行：pending_line（贴在输入框上方，随着重绘保持位置）
      第二行：真实输入提示符（busy/ready 两种样式）
    message 支持 callable + formatted text。:contentReference[oaicite:2]{index=2}
    """
    parts = []

    if state.pending_line:
        parts.append(("class:pending", "\n" + state.pending_line))
        parts.append(("", "\n"))

    if state.streaming:
        parts.append(("class:prompt.busy", "… "))
        parts.append(("class:prompt.busy", "> "))
    else:
        parts.append(("class:prompt.ready", "> "))

    return FormattedText(parts)


def bottom_toolbar():
    """
    可选：底部状态条（在输入行下面）。底部工具条也支持 callable 动态返回。:contentReference[oaicite:3]{index=3}
    """
    if state.streaming or state.queued:
        return FormattedText([
            ("class:toolbar", f" streaming={state.streaming}  queued={state.queued}  (Ctrl-C to exit) ")
        ])
    return FormattedText([("class:toolbar", " ready  (Ctrl-C to exit) ")])


style = Style.from_dict({
    "prompt.ready": "bold",
    "prompt.busy": "bold ansiyellow",
    "pending": "ansiblue",
    "toolbar": "reverse",
})


async def fake_llm_stream(text: str):
    """
    模拟：把 text 作为一次请求，流式输出 token。
    真实场景：替换成你的 LLM streaming 回调即可。
    """
    # 这里用 stdout 直接写；在 patch_stdout 作用域内不会打乱输入行。:contentReference[oaicite:4]{index=4}
    sys.stdout.write("[agent] ")
    sys.stdout.flush()

    for tok in ["收到：", text, "。", "（流式输出中）", "\n"] * 10:
        await asyncio.sleep(0.2)
        print(tok)
        # sys.stdout.write(tok)
        # sys.stdout.flush()


async def agent_worker():
    """
    消费 outbox：顺序处理用户输入。
    在处理期间：state.streaming=True，prompt 样式变 busy，pending_line 保持显示。
    """
    while True:
        text = await outbox.get()
        # 进入 streaming 状态
        state.streaming = True
        state.queued = outbox.qsize()
        invalidate()

        try:
            await fake_llm_stream(text)
        finally:
            # 一次回复结束：如果队列为空，就退出 streaming，并清掉 pending_line
            state.queued = outbox.qsize()
            if state.queued == 0:
                state.streaming = False
                state.pending_line = None
            invalidate()
            outbox.task_done()


async def main():
    session = PromptSession(
        message=prompt_message,
        bottom_toolbar=bottom_toolbar,
        style=style,
    )

    # 启动 Agent 消费者
    asyncio.create_task(agent_worker())

    # 关键：patch_stdout 保证后台输出不会破坏 prompt。:contentReference[oaicite:5]{index=5}
    with patch_stdout():
        while True:
            try:
                user = await session.prompt_async()
            except (EOFError, KeyboardInterrupt):
                break

            user = user.strip()
            if not user:
                continue

            # 1) 把用户输入写入“对话记录”（进入终端 scrollback）
            print(f"[you] {user}")

            # 2) 更新 pending_line：贴在输入框上方，且在流式输出期间保持“粘住”
            #    可按你的语义改成：已发送/排队/待处理/已取消等。
            if state.streaming or outbox.qsize() > 0:
                state.pending_line = f"(queued) {user}"
            else:
                state.pending_line = f"(sent) {user}"
            invalidate()

            # 3) 入队：即使 agent 还在输出，用户也能继续输入下一条
            await outbox.put(user)
            state.queued = outbox.qsize()
            invalidate()

    print("bye.")


if __name__ == "__main__":
    asyncio.run(main())
