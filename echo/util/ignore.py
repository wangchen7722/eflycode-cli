import fnmatch
from typing import List
from pathlib import Path

from loguru import logger


class IgnoreManager:
    """文件忽略管理器"""
    
    def __init__(self):
        self.ignore_filename = ".echoignore"
    
    def load_ignore_patterns(self, base_path: str = ".echo") -> List[str]:
        """加载忽略模式
        
        Args:
            base_path: 基础路径，用于查找.echoignore文件
            
        Returns:
            忽略模式列表
        """
        patterns = []
        
        # 查找.echoignore文件
        ignore_file_path = Path(base_path) / self.ignore_filename
        
        if ignore_file_path.exists() and ignore_file_path.is_file():
            try:
                with open(ignore_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # 跳过空行和注释行
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except Exception as e:
                logger.warning("无法读取.echoignore文件", e)
        
        return patterns
    
    def should_ignore(self, file_path: str, patterns: List[str]) -> bool:
        """检查文件是否应该被忽略
        
        Args:
            file_path: 文件路径
            patterns: 忽略模式列表
            
        Returns:
            是否应该忽略该文件
        """
        path_obj = Path(file_path)
        
        # 检查文件名和路径的各个部分
        for pattern in patterns:
            # 去除模式末尾的斜杠（用于目录匹配）
            clean_pattern = pattern.rstrip("/")
            
            # 检查完整路径
            if fnmatch.fnmatch(str(path_obj), pattern) or fnmatch.fnmatch(str(path_obj), clean_pattern):
                return True
            
            # 检查文件名
            if fnmatch.fnmatch(path_obj.name, pattern) or fnmatch.fnmatch(path_obj.name, clean_pattern):
                return True
            
            # 检查路径中的任何部分
            for part in path_obj.parts:
                if fnmatch.fnmatch(part, pattern) or fnmatch.fnmatch(part, clean_pattern):
                    return True
                    
            # 特殊处理目录模式（以/结尾）
            if pattern.endswith("/") and path_obj.is_dir():
                if fnmatch.fnmatch(path_obj.name, clean_pattern):
                    return True
        
        return False