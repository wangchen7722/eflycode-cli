"""会话存储

负责保存和恢复会话消息
"""

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from eflycode.core.constants import EFLYCODE_DIR, SESSIONS_DIR
from eflycode.core.config.config_manager import resolve_workspace_dir
from eflycode.core.llm.protocol import Message
from eflycode.core.utils.logger import logger


class SessionStore:
    """会话存储单例"""

    _instance: Optional["SessionStore"] = None

    def __init__(self, workspace_dir: Optional[Path] = None):
        """初始化会话存储"""
        self._workspace_dir = workspace_dir or resolve_workspace_dir()
        self._sessions_dir = self._workspace_dir / EFLYCODE_DIR / SESSIONS_DIR
        if not self._is_test_environment():
            self._sessions_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_instance(cls) -> "SessionStore":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_session_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.json"

    def save(self, session: Any) -> None:
        """保存会话到磁盘"""
        if self._is_test_environment():
            return
        try:
            messages = session.get_messages()
            last_user_message_preview = ""
            for msg in reversed(messages):
                if msg.role == "user" and msg.content:
                    last_user_message_preview = self._summarize_text(msg.content, 200)
                    break
            data = {
                "id": session.id,
                "initial_user_question": session.initial_user_question,
                "message_count": len(messages),
                "last_user_message_preview": last_user_message_preview,
                "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "messages": [msg.model_dump() for msg in messages],
            }
            session_path = self._get_session_path(session.id)
            session_path.write_text(
                json.dumps(data, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存会话失败: session_id={getattr(session, 'id', '')}, error={e}")

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """加载会话数据"""
        if self._is_test_environment():
            return None
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None

        try:
            data = json.loads(session_path.read_text(encoding="utf-8"))
            raw_messages = data.get("messages", [])
            messages: List[Message] = [Message(**msg) for msg in raw_messages]
            return {
                "id": data.get("id", session_id),
                "initial_user_question": data.get("initial_user_question"),
                "message_count": data.get("message_count"),
                "last_user_message_preview": data.get("last_user_message_preview"),
                "updated_at": data.get("updated_at"),
                "messages": messages,
            }
        except Exception as e:
            logger.warning(f"加载会话失败: session_id={session_id}, error={e}")
            return None

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出最近的会话"""
        if self._is_test_environment():
            return []
        entries: List[Dict[str, Any]] = []
        for session_path in sorted(
            self._sessions_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                raw = json.loads(session_path.read_text(encoding="utf-8"))
                session_id = raw.get("id") or session_path.stem
                entries.append(
                    {
                        "id": session_id,
                        "initial_user_question": raw.get("initial_user_question"),
                        "message_count": raw.get("message_count"),
                        "last_user_message_preview": raw.get("last_user_message_preview"),
                        "updated_at": raw.get("updated_at"),
                    }
                )
            except Exception:
                continue
            if len(entries) >= limit:
                break
        return entries

    @staticmethod
    def _summarize_text(text: str, limit: int) -> str:
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...({len(text)} chars)"

    @staticmethod
    def _is_test_environment() -> bool:
        return os.getenv("EFLYCODE_TESTING") == "1"
