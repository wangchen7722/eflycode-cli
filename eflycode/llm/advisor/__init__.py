from .base_advisor import *
from .environment_advisor import EnvironmentAdvisor
from .tool_call_advisor import ToolCallAdvisor

def initialize_builtin_advisors():
    """初始化内置的 Advisors"""
    register_advisor("buildin_environment_advisor", EnvironmentAdvisor)
    register_advisor("buildin_tool_call_advisor", ToolCallAdvisor)