import os
from echo.tools.base_tool import BaseTool

class ExecuteCommandTool(BaseTool):
    """执行命令的工具"""

    NAME = "exec_command"
    DESCRIPTION = """
    Request to execute a CLI command on the system. Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task. 
    You must tailor your command to the user's system and provide a clear explanation of what the command does. 
    For command chaining, use the appropriate chaining syntax for the user's shell. Prefer to execute complex CLI commands over creating executable scripts, as they are more flexible and easier to run. 
    Prefer relative commands and paths that avoid location sensitivity for terminal consistency, e.g: `touch ./testdata/example.file`, `dir ./examples/model1/data/yaml`, or `go test ./cmd/front --config ./cmd/front/config.yml`. 
    If directed by the user, you may open a terminal in a different directory by using the `cwd` parameter.
    """
    PARAMETERS = {
        ""
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The CLI command to execute. This should be valid for the current operating system. Ensure the command is properly formatted and does not contain any harmful instructions.",
            },
            "cwd": {
                "type": "string",
                "description": f"The working directory to execute the command in default ({os.getcwd()}).",
            }
        },
        "required": ["command"],
    }
    EXAMPLES = {
        "Requesting to execute ls in a specific directory if directed": {
            "type": "function",
            "name": "exec_command",
            "parameters": {
                "command": "ls",
                "cwd": "/path/to/directory",
            }
        },
        "Requesting to execute pip install -r requirements.txt": {
            "type": "function",
            "name": "exec_command",
            "parameters": {
                "command": "pip install -r requirements.txt",
            }
        }
    }
