import json
from typing import List

from echo.schema.llm import ToolCall


def _apply_tool_call_template(tool_call: ToolCall):
    tool_call_args = []
    # NOTE: 由于 tool_call 是由程序生成，而非模型返回，故可以保证其参数是合法的 JSON 字符串
    arguments = json.loads(tool_call["function"]["arguments"])
    for arg_key, arg_value in arguments.items():
        tool_call_args.append(f"<{arg_key}>{arg_value}</{arg_key}>")
    return "<{tool_call_name}>{tool_call_args}</{tool_call_name}>".format(
        tool_call_name=tool_call["function"]["name"], tool_call_args="".join(tool_call_args)
    )


def apply_tool_calls_template(tool_calls: List[ToolCall]):
    return "\n".join([_apply_tool_call_template(tool_call) for tool_call in tool_calls])
