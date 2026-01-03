"""全局UI配色方案模块

提供统一的配色定义，支持prompt_toolkit和rich库的样式配置。
"""

from rich.theme import Theme
from prompt_toolkit.styles import Style as PTKStyle

# 全局UI配色方案
UI_COLORS = {
    # 主要交互元素 - 采用柔和但醒目的颜色
    "prompt": "#ffffff",           # 提示符：紫罗兰色，现代且专业
    "input": "#f8fafc",           # 输入文本：极浅灰白，柔和护眼
    "border": "#475569",          # 边框：石板灰，低调不突兀
    
    # 辅助信息元素
    "shortcut": "#00afff",        # 快捷键提示：中性石板灰
    "placeholder": "#5A5A5A",     # 占位符：浅石板灰，引导性
    
    # 状态和反馈元素
    "success": "#10b981",         # 成功状态：翠绿色，清新自然
    "warning": "#f59e0b",         # 警告状态：琥珀色，温和警示
    "error": "#ef4444",           # 错误状态：珊瑚红，醒目但不刺眼
    "info": "#3b82f6",            # 信息提示：天蓝色，友好亲和
    
    # 代码语法高亮
    "code": "#f97316",            # 代码块：橙色，温暖醒目
    "keyword": "#a855f7",         # 关键字：紫色，优雅突出
    "string": "#22c55e",          # 字符串：绿色，自然清新
    "comment": "#6b7280",         # 注释：中性灰，不干扰阅读
    "function": "#06b6d4",        # 函数名：青色，清晰识别
    "variable": "#e11d48",        # 变量：玫瑰红，易于区分
    "number": "#f472b6",          # 数字：粉色，柔和突出
    "operator": "#8b5cf6",        # 操作符：紫色，逻辑清晰
}

# prompt_toolkit样式配置
PTK_STYLE = PTKStyle.from_dict({
    # 主要交互元素
    "prompt": f"{UI_COLORS['prompt']} bold",
    "input": UI_COLORS["input"],
    "frame.border": UI_COLORS["border"],
    
    # 辅助信息元素
    "shortcut": f"{UI_COLORS['shortcut']} bold",
    # "bottom-toolbar": "#ffffff",
    # "bottom-toolbar.key": "bg:#5a5a5a bold",
    # "bottom-toolbar.label": "#d0d0d0 bold",
    # "bottom-toolbar.sep": "#d0d0d0 bold",
    "placeholder": f"{UI_COLORS['placeholder']}",

    # 补全菜单样式
    "completion-menu": "bg:#1e1e1e",
    "completion-menu.completion": "bg:#2a2a2a fg:#cccccc",
    "completion-menu.completion.current": "bg:#555555 fg:#ffffff",
    "completion-menu.meta": "fg:#808080",
    "completion-menu.multi-column-meta": "fg:#606060",
    "scrollbar.background": "bg:#2a2a2a",
    "scrollbar.button": "bg:#666666",
    
    # 状态和反馈元素
    "success": f"{UI_COLORS['success']} bold",
    "warning": f"{UI_COLORS['warning']} bold",
    "error": f"{UI_COLORS['error']} bold",
    "info": f"{UI_COLORS['info']} bold",
    "toolbar.key": "bold #9ca3af",
    "toolbar.label": "#d1d5db",
    
    # 代码语法高亮
    "code": f"{UI_COLORS['code']} bold",
    "keyword": f"{UI_COLORS['keyword']} bold",
    "string": UI_COLORS["string"],
    "comment": f"{UI_COLORS['comment']} italic",
    "function": f"{UI_COLORS['function']} bold",
    "variable": UI_COLORS["variable"],
    "number": UI_COLORS["number"],
    "operator": f"{UI_COLORS['operator']} bold",

    # 闪烁文本组件
    "glowing.text.normal": "fg:#777777",
    "glowing.text.near": "fg:#dddddd",
    "glowing.text.far": "fg:#aaaaaa",
    "glowing.text.center": "fg:#ffffff bold",
    "glowing.text.paused": "fg:#777777",
})

# rich主题配置
RICH_THEME = Theme({
    # 主要交互元素
    "prompt": UI_COLORS["prompt"],
    "input": UI_COLORS["input"],
    "border": UI_COLORS["border"],
    
    # 辅助信息元素
    "shortcut": UI_COLORS["shortcut"],
    "placeholder": UI_COLORS["placeholder"],
    
    # 状态和反馈元素
    "success": UI_COLORS["success"],
    "warning": UI_COLORS["warning"],
    "error": UI_COLORS["error"],
    "info": UI_COLORS["info"],
    
    # 代码语法高亮
    "code": UI_COLORS["code"],
    "keyword": UI_COLORS["keyword"],
    "string": UI_COLORS["string"],
    "comment": UI_COLORS["comment"],
    "function": UI_COLORS["function"],
    "variable": UI_COLORS["variable"],
    "number": UI_COLORS["number"],
    "operator": UI_COLORS["operator"],
})