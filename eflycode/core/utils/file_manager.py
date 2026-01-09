"""文件管理与模糊匹配

负责索引项目文件，并提供基于忽略规则的模糊匹配。
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Iterable, Optional, Tuple

from eflycode.core.config import resolve_workspace_dir
from eflycode.core.config.ignore import load_all_ignore_patterns, should_ignore_path


class FileManager:
    """项目文件索引与模糊匹配管理器"""

    def __init__(
        self,
        workspace_dir: Path,
        refresh_interval: float = 2.0,
        watch_interval: float = 1.0,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._refresh_interval = refresh_interval
        self._watch_interval = watch_interval
        self._cache: list[str] = []
        self._cache_time: float = 0.0
        self._lock = threading.Lock()
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_stop = threading.Event()
        self._snapshot: dict[str, Tuple[int, int]] = {}

    @property
    def workspace_dir(self) -> Path:
        return self._workspace_dir

    def get_files(self) -> list[str]:
        self._refresh_if_needed()
        return list(self._cache)

    def fuzzy_find(self, query: str, limit: int = 200) -> list[str]:
        self._refresh_if_needed()
        if not query:
            return self._cache[:limit]

        matches: list[tuple[tuple[int, int], str]] = []
        for path in self._cache:
            score = self._fuzzy_score(query, path)
            if score is not None:
                matches.append((score, path))
        matches.sort(key=lambda item: item[0])
        return [path for _, path in matches[:limit]]

    def _refresh_if_needed(self) -> None:
        now = time.monotonic()
        if self._cache and (now - self._cache_time) < self._refresh_interval:
            return
        with self._lock:
            now = time.monotonic()
            if self._cache and (now - self._cache_time) < self._refresh_interval:
                return
            self._cache = self._scan_files()
            self._cache_time = now

    def _scan_files(self) -> list[str]:
        ignore_patterns = load_all_ignore_patterns(
            workspace_dir=self._workspace_dir, require_git_repo=False
        )
        default_excludes = {".git", "__pycache__", "node_modules", ".venv"}
        files: list[str] = []

        for root, dirs, filenames in os.walk(self._workspace_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if d not in default_excludes]
            if ignore_patterns:
                dirs[:] = [
                    d
                    for d in dirs
                    if not should_ignore_path(root_path / d, ignore_patterns, self._workspace_dir)
                ]
            for filename in filenames:
                path = root_path / filename
                if ignore_patterns and should_ignore_path(path, ignore_patterns, self._workspace_dir):
                    continue
                rel_path = path.relative_to(self._workspace_dir).as_posix()
                files.append(rel_path)

        return files

    @staticmethod
    def _fuzzy_score(query: str, candidate: str) -> Optional[tuple[int, int]]:
        query_lower = query.lower()
        candidate_lower = candidate.lower()
        index = -1
        gaps = 0

        for ch in query_lower:
            next_index = candidate_lower.find(ch, index + 1)
            if next_index == -1:
                return None
            gaps += next_index - index - 1
            index = next_index

        return (gaps, len(candidate))

    def start_watching(self) -> None:
        """启动文件变更轮询监控（跨平台）"""
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._watch_stop.clear()
        self._watch_thread = threading.Thread(
            target=self._watch_loop, name="FileManagerWatcher", daemon=True
        )
        self._watch_thread.start()

    def stop_watching(self) -> None:
        """停止文件变更轮询监控"""
        self._watch_stop.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=1.0)

    def _watch_loop(self) -> None:
        while not self._watch_stop.is_set():
            try:
                changed = self._scan_snapshot_changed()
                if changed:
                    with self._lock:
                        self._cache = self._scan_files()
                        self._cache_time = time.monotonic()
                self._watch_stop.wait(self._watch_interval)
            except Exception:
                self._watch_stop.wait(self._watch_interval)

    def _scan_snapshot_changed(self) -> bool:
        ignore_patterns = load_all_ignore_patterns(
            workspace_dir=self._workspace_dir, require_git_repo=False
        )
        default_excludes = {".git", "__pycache__", "node_modules", ".venv"}
        current: dict[str, Tuple[int, int]] = {}

        for root, dirs, filenames in os.walk(self._workspace_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if d not in default_excludes]
            if ignore_patterns:
                dirs[:] = [
                    d
                    for d in dirs
                    if not should_ignore_path(root_path / d, ignore_patterns, self._workspace_dir)
                ]
            for filename in filenames:
                path = root_path / filename
                if ignore_patterns and should_ignore_path(path, ignore_patterns, self._workspace_dir):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rel_path = path.relative_to(self._workspace_dir).as_posix()
                current[rel_path] = (int(stat.st_mtime), int(stat.st_size))

        if current != self._snapshot:
            self._snapshot = current
            return True
        return False


_default_file_manager: Optional[FileManager] = None


def get_file_manager(workspace_dir: Optional[Path] = None) -> FileManager:
    global _default_file_manager
    workspace_dir = workspace_dir or resolve_workspace_dir()
    if _default_file_manager is None or _default_file_manager.workspace_dir != workspace_dir:
        _default_file_manager = FileManager(workspace_dir)
        _default_file_manager.start_watching()
    return _default_file_manager
