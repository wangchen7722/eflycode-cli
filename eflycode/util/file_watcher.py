"""
文件监听器

监听配置文件变化并触发回调
"""

import hashlib
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from threading import Thread, Lock

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class FileWatcher:
    """文件变化监听器"""
    
    def __init__(self):
        self._callbacks: Dict[str, List[Callable[[str], None]]] = {}
        self._observer: Optional[Observer] = None
        self._lock = Lock()
        self._last_modified: Dict[str, float] = {}
        # 哈希跟踪：用于区分程序修改和用户修改
        self._file_hashes: Dict[str, str] = {}
        self._expected_hashes: Dict[str, str] = {}
        
    def add_file(self, file_path: str, callback: Callable[[str], None]) -> None:
        """
        添加要监听的文件
        
        Args:
            file_path: 文件路径
            callback: 文件变化时的回调函数
        """
        with self._lock:
            if file_path not in self._callbacks:
                self._callbacks[file_path] = []
            self._callbacks[file_path].append(callback)
            # 初始化文件哈希
            self._initialize_file_hash(file_path)
            
    def remove_file(self, file_path: str) -> None:
        """
        移除监听的文件
        
        Args:
            file_path: 文件路径
        """
        with self._lock:
            self._callbacks.pop(file_path, None)
            self._last_modified.pop(file_path, None)
            self._file_hashes.pop(file_path, None)
            self._expected_hashes.pop(file_path, None)
            
    def start(self) -> None:
        """开始监听"""
        if not WATCHDOG_AVAILABLE:
            # 如果没有watchdog，使用轮询方式
            self._start_polling()
            return
            
        if self._observer is not None:
            return
            
        self._observer = Observer()
        
        # 为每个文件的目录创建监听器
        watched_dirs = set()
        for file_path in self._callbacks.keys():
            dir_path = str(Path(file_path).parent)
            if dir_path not in watched_dirs:
                handler = FileEventHandler(self)
                self._observer.schedule(handler, dir_path, recursive=False)
                watched_dirs.add(dir_path)
        
        self._observer.start()
        
    def stop(self) -> None:
        """停止监听"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            
    def _start_polling(self) -> None:
        """启动轮询监听（fallback方案）"""
        def poll():
            while self._callbacks:
                for file_path in list(self._callbacks.keys()):
                    if Path(file_path).exists():
                        mtime = Path(file_path).stat().st_mtime
                        if file_path not in self._last_modified:
                            self._last_modified[file_path] = mtime
                        elif mtime > self._last_modified[file_path]:
                            self._last_modified[file_path] = mtime
                            # 检查是否为程序修改
                            if self._is_programmatic_change(file_path):
                                # 程序修改，更新哈希但不触发回调
                                self._update_file_hash(file_path)
                            else:
                                # 用户修改，触发回调
                                self._trigger_callbacks(file_path)
                time.sleep(1)
        
        thread = Thread(target=poll, daemon=True)
        thread.start()
        
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        计算文件的 MD5 哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件的 MD5 哈希值
        """
        try:
            with open(file_path, "rb") as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except (OSError, IOError):
            return ""
    
    def _initialize_file_hash(self, file_path: str) -> None:
        """
        初始化文件哈希值
        
        Args:
            file_path: 文件路径
        """
        if Path(file_path).exists():
            hash_value = self._calculate_file_hash(file_path)
            self._file_hashes[file_path] = hash_value
    
    def _update_file_hash(self, file_path: str) -> None:
        """
        更新文件哈希值
        
        Args:
            file_path: 文件路径
        """
        if Path(file_path).exists():
            hash_value = self._calculate_file_hash(file_path)
            self._file_hashes[file_path] = hash_value
            # 清除预期哈希，因为文件已经被更新
            self._expected_hashes.pop(file_path, None)
    
    def _is_programmatic_change(self, file_path: str) -> bool:
        """
        判断文件变化是否为程序修改
        
        Args:
            file_path: 文件路径
            
        Returns:
            True 如果是程序修改，False 如果是用户修改
        """
        if not Path(file_path).exists():
            return False
            
        current_hash = self._calculate_file_hash(file_path)
        expected_hash = self._expected_hashes.get(file_path)
        
        # 如果当前哈希与预期哈希匹配，说明是程序修改
        if expected_hash and current_hash == expected_hash:
            return True
        
        return False
    
    def set_expected_hash(self, file_path: str) -> None:
        """
        在程序修改文件前设置预期哈希值
        
        Args:
            file_path: 文件路径
        """
        with self._lock:
            if Path(file_path).exists():
                # 计算修改后的预期哈希值
                # 这里需要在实际修改文件后调用，或者传入修改后的内容
                hash_value = self._calculate_file_hash(file_path)
                self._expected_hashes[file_path] = hash_value
    
    def set_expected_hash_for_content(self, file_path: str, content: str) -> None:
        """
        为即将写入的内容设置预期哈希值
        
        Args:
            file_path: 文件路径
            content: 即将写入的内容
        """
        with self._lock:
            hash_value = hashlib.md5(content.encode("utf-8")).hexdigest()
            self._expected_hashes[file_path] = hash_value
        
    def _trigger_callbacks(self, file_path: str) -> None:
        """触发文件变化回调"""
        with self._lock:
            # 更新文件哈希
            self._update_file_hash(file_path)
            
            callbacks = self._callbacks.get(file_path, [])
            for callback in callbacks:
                try:
                    callback(file_path)
                except Exception as e:
                    print(f"文件监听回调执行失败: {e}")


class FileEventHandler(FileSystemEventHandler):
    """文件事件处理器"""
    
    def __init__(self, watcher: FileWatcher):
        self.watcher = watcher
        self._last_trigger: Dict[str, float] = {}
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        file_path = event.src_path
        
        # 防抖处理
        now = time.time()
        if file_path in self._last_trigger:
            if now - self._last_trigger[file_path] < 0.5:
                # 500ms内的重复事件忽略
                return
        self._last_trigger[file_path] = now
        
        # 检查是否是我们监听的文件
        if file_path in self.watcher._callbacks:
            # 检查是否为程序修改
            if self.watcher._is_programmatic_change(file_path):
                # 程序修改，更新哈希但不触发回调
                self.watcher._update_file_hash(file_path)
            else:
                # 用户修改，触发回调
                self.watcher._trigger_callbacks(file_path)