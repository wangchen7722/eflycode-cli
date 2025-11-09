import re
import importlib
import pkgutil
from typing import Dict, Type, Optional, Any

from eflycode.llm.advisor.base_advisor import Advisor


def camel_to_snake(name: str) -> str:
    """将驼峰命名转为下划线命名

    Args:
        name: 驼峰命名字符串

    Returns:
        转换后的下划线命名字符串
    """

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class AdvisorRegistry:
    """Advisor 注册中心

    职责：
    - 扫描并注册指定包中的 Advisor 类
    - 提供按名称获取 Advisor 类的能力
    - 支持覆盖注册与清空注册表
    """

    _instance: Optional["AdvisorRegistry"] = None

    def __init__(self) -> None:
        """初始化注册中心

        扫描内置 Advisor 包并完成注册
        """

        if not hasattr(self, "_initialized"):
            self._advisors: Dict[str, Type[Advisor]] = {}
            self._scanned_packages: set[str] = set()
            self.scan_advisors("eflycode.llm.advisor")
            self._initialized = True

    def __new__(cls) -> "AdvisorRegistry":
        """单例构造函数"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def scan_advisors(self, package_name: str) -> None:
        """扫描指定包中的所有 Advisor 类

        Args:
            package_name: 包名，例如 'eflycode.llm.advisor'
        """

        if package_name in self._scanned_packages:
            return

        package = importlib.import_module(package_name)

        # 如果单文件模块, 直接扫描
        if not hasattr(package, "__path__"):
            self._scan_module(package, Advisor)
        else:
            # 递归扫描包下所有模块
            for _, name, is_pkg in pkgutil.walk_packages(
                package.__path__, package.__name__ + "."
            ):
                mod = importlib.import_module(name)
                self._scan_module(mod, Advisor)

        self._scanned_packages.add(package_name)

    def _scan_module(self, module: Any, base_class: Type[Advisor]) -> None:
        """扫描模块中的 Advisor 类并注册

        Args:
            module: 模块对象
            base_class: 基类，用于筛选 Advisor 类
        """

        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, base_class) and obj is not base_class:
                advisor_name = camel_to_snake(name)

                # 标记是否为系统内置 Advisor
                is_builtin = module.__name__.startswith("eflycode.llm.advisor")
                if is_builtin:
                    self.register(f"buildin_{advisor_name}", obj)

                self.register(advisor_name, obj)

    def register(self, name: str, clazz: Type[Advisor], overwrite: bool = False) -> None:
        """注册 Advisor 类

        Args:
            name: Advisor 名称
            clazz: Advisor 类
            overwrite: 是否覆盖已存在的注册，默认 False

        Raises:
            ValueError: 当名称已存在且不允许覆盖时
        """

        if not overwrite and name in self._advisors:
            raise ValueError(f"Advisor 名称 '{name}' 已存在，无法注册")

        self._advisors[name] = clazz

    def get_advisor_class(self, name: str) -> Type[Advisor]:
        """根据名称获取 Advisor 类

        Args:
            name: Advisor 名称

        Returns:
            Advisor 类

        Raises:
            KeyError: 当 Advisor 名称不存在时
        """

        if name not in self._advisors:
            available = list(self._advisors.keys())
            raise KeyError(
                f"未找到名称为 '{name}' 的Advisor。可用的Advisor: {available}"
            )
        return self._advisors[name]

    def list_advisors(self) -> Dict[str, Type[Advisor]]:
        """列出所有已注册的 Advisor

        Returns:
            包含所有已注册 Advisor 的字典
        """

        return self._advisors.copy()

    def contain_advisor(self, name: str) -> bool:
        """检查是否包含指定名称的 Advisor

        Args:
            name: Advisor 名称

        Returns:
            是否存在该 Advisor
        """

        return name in self._advisors

    def clear(self) -> None:
        """清空注册表"""
        self._advisors.clear()

    @classmethod
    def register_advisor(cls, name: str, advisor_class: Type[Advisor], overwrite: bool = False) -> None:
        """类方法包装：注册 Advisor 类"""
        instance = cls()
        instance.register(name, advisor_class, overwrite)

    @classmethod
    def get_advisor(cls, name: str) -> Type[Advisor]:
        """类方法包装：获取 Advisor 类"""
        instance = cls()
        return instance.get_advisor_class(name)

    @classmethod
    def contain_advisor_name(cls, name: str) -> bool:
        """类方法包装：检查 Advisor 是否存在"""
        instance = cls()
        return instance.contain_advisor(name)

    @classmethod
    def clear_registry(cls) -> None:
        """类方法包装：清空注册表"""
        instance = cls()
        instance.clear()


def initialize_advisors() -> None:
    """初始化并扫描内置 Advisor

    为应用启动阶段提供显式初始化入口
    """

    AdvisorRegistry()