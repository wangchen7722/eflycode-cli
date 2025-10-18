from .base_advisor import *
from .environment_advisor import EnvironmentAdvisor
from .logging_advisor import LoggingAdvisor
from .tool_call_advisor import ToolCallAdvisor


def initialize_builtin_advisors():
    """初始化内置的 Advisors"""
    register_advisor("buildin_environment_advisor", EnvironmentAdvisor, overwrite=True)
    register_advisor("buildin_tool_call_advisor", ToolCallAdvisor, overwrite=True)
    register_advisor("buildin_logging_advisor", LoggingAdvisor, overwrite=True)


def initialize_advisors():
    """初始化所有 Advisors"""
    clear_advisors()
    initialize_builtin_advisors()
