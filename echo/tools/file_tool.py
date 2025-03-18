from echo.tools.base_tool import BaseTool

class ReadFileTool(BaseTool):
    """读取文件工具类"""
    NAME = "read_file"
    DESCRIPTION = """
    Request to read the contents of a file at the specified path. 
    Use this when you need to examine the contents of an existing file you do not know the contents of, for example to analyze code, review text files, or extract information from configuration files. 
    The output includes line numbers prefixed to each line (e.g. "1 | const x = 1")
    """.replace("\n", "")
    PARAMETERS = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to read",
            }
        },
        "required": ["path"],
    }
    
    def run(self, path: str, **kwargs) -> str:
        """执行读取文件的操作"""
        with open(path, "r") as f:
            lines = f.readlines()
        return "\n".join([f"{i+1} | {line}" for i, line in enumerate(lines)])