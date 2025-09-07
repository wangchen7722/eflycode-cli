from abc import ABC, abstractmethod
from typing import List, Literal, Optional, Sequence, Dict, Any, Generator


class BaseUI(ABC):
    """用户界面基类，定义所有UI实现必须遵循的接口
    
    这个抽象基类定义了用户界面的核心功能接口，包括：
    - 基础显示功能：信息输出、错误提示、成功提示等
    - 用户交互功能：输入获取、选择列表等
    - 高级显示功能：面板、表格、进度条等
    - 系统控制功能：清屏、刷新、退出等
    
    所有具体的UI实现类都应该继承此基类并实现所有抽象方法。
    """

    @abstractmethod
    def print(self, text: str) -> None:
        """打印文本到控制台
        
        Args:
            text: 要打印的文本内容
        """
        pass
    
    @abstractmethod
    def info(self, text: str, **kwargs) -> None:
        """显示信息内容
        
        Args:
            text: 要显示的信息内容
            **kwargs: 额外的显示参数
        """
        pass
    
    @abstractmethod
    def error(self, message: str) -> None:
        """显示错误信息
        
        Args:
            message: 错误信息
        """
        pass
    
    @abstractmethod
    def success(self, message: str) -> None:
        """显示成功信息
        
        Args:
            message: 成功信息
        """
        pass
    
    @abstractmethod
    def warning(self, message: str) -> None:
        """显示警告信息
        
        Args:
            message: 警告信息
        """
        pass
    
    # 用户交互方法
    @abstractmethod
    def acquire_user_input(self, text: str = "", choices: Optional[List[str]] = None) -> str:
        """获取用户输入
        
        Args:
            text: 输入框占位符文本
            choices: 可选的备选项列表，若提供则启用自动补全
        
        Returns:
            用户输入的内容
        
        Raises:
            KeyboardInterrupt: 用户取消输入时抛出
        """
        pass
    
    @abstractmethod
    def choices(self, tip: str, choices: List[str]) -> str:
        """提供一个选择列表供用户选择
        
        Args:
            tip: 提示文本
            choices: 选项列表，不可为空
        
        Returns:
            用户选择的结果，若用户取消或未选择则返回空字符串
        
        Raises:
            ValueError: 当选项列表为空时抛出
        """
        pass
    
    # 高级显示方法
    @abstractmethod
    def panel(self, titles: Sequence[str], content: str, color: str = "green",
              align: Literal["default", "left", "center", "right", "full"] = "default",
              style: Optional[str] = None) -> None:
        """显示面板
        
        Args:
            titles: 面板标题列表，多个标题将以分隔符连接
            content: 面板内容，将显示在面板主体部分
            color: 面板边框颜色，默认为绿色
            align: 内容对齐方式
            style: 边框样式
        """
        pass
    
    @abstractmethod
    def table(self, title: str, columns: List[str], rows: List[List[str]]) -> None:
        """显示表格内容
        
        Args:
            title: 表格标题
            columns: 列名列表
            rows: 行数据列表
        
        Raises:
            ValueError: 当列数和行数不匹配时抛出
        """
        pass
    
    @abstractmethod
    def progress(self, description: str, iterable, total=None) -> Generator[Any, None, None]:
        """显示进度条并迭代处理数据
        
        Args:
            description: 进度条描述
            iterable: 可迭代对象
            total: 总数量，如果不提供则尝试从iterable获取长度
        
        Yields:
            迭代器中的每个元素
        """
        pass
    
    @abstractmethod
    def help(self, commands: List[Dict[str, str]]) -> None:
        """显示帮助信息
        
        Args:
            commands: 命令列表，每个元素为包含命令信息的字典
        """
        pass
    
    # 系统控制方法
    @abstractmethod
    def welcome(self) -> None:
        """显示欢迎信息"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """清空屏幕"""
        pass
    
    @abstractmethod
    def flush(self) -> None:
        """刷新输出"""
        pass
    
    @abstractmethod
    def exit(self) -> None:
        """退出程序"""
        pass
    
    # 可选的实例获取方法，子类可以选择实现
    @classmethod
    def get_instance(cls):
        """获取UI实例
        
        这是一个可选方法，子类可以选择实现单例模式或其他实例管理方式。
        默认实现会抛出NotImplementedError。
        
        Returns:
            UI实例
        
        Raises:
            NotImplementedError: 子类未实现此方法时抛出
        """
        raise NotImplementedError("子类应该实现get_instance方法")