import glob
import os
from typing import Dict, List

from tree_sitter import Node
from tree_sitter_languages import get_parser

from echo.tool.base_tool import BaseTool


class ListCodeDefinitionsTool(BaseTool):
    
    @property
    def name(self) -> str:
        return "list_code_definitions"
    
    @property
    def type(self) -> str:
        return "function"
    
    @property
    def is_approval(self) -> bool:
        return False
    
    @property
    def description(self) -> str:
        return """
    Request to list definition names (classes, functions, methods, etc.) used in source code files at the top level of the specified directory. 
    This tool provides insights into the codebase structure and important constructs, encapsulating high-level concepts and relationships that are crucial for understanding the overall architecture.
    This tool ONLY supports [python] at the moment.
    """
    
    def display(self, **kwargs) -> str:
        return "列出代码定义"
    
    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file or directory containing the source code files."
                },
                "language": {
                    "type": "array",
                    "description": "The programming language of the source code files.",
                    "items": {
                        "type": "string",
                        "enum": [
                            "python",
                        ]
                    }
                },
                "pattern": {
                    "type": "string",
                    "description": "The pattern to match the source code files."
                }
            },
            "required": ["path", "language", "pattern"]
        }
    @property
    def examples(self):
        return {
            "Requesting to list all top level python source code definitions in the src directory": {
                "type": self.type,
                "name": self.name,
                "arguments": {
                    "path": "src",
                    "language": ["python"],
                    "pattern": "**/*.py"
                }
            }
        }
    
    def get_definition_name(self, node: Node) -> str | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        if not name_node.text:
            return None
        return name_node.text.decode("utf-8")
    
    def find_python_definitions(self, root: Node) -> Dict[str, List[str]]:
        definition = {
            "classes": [],
            "methods": [],
            "functions": [],
            "globals": []
        }
        for child in root.children:
            if child.type == "class_definition":
                name = self.get_definition_name(child)
                if not name:
                    continue
                definition["classes"].append(name)
            elif child.type == "function_definition":
                name = self.get_definition_name(child)
                if not name:
                    continue
                definition["functions"].append(name)
            elif child.type == "method_definition":
                name = self.get_definition_name(child)
                if not name:
                    continue
                definition["methods"].append(name)
            elif child.type == "expression_statement":
                name = self.get_definition_name(child)
                if not name:
                    continue
                definition["globals"].append(name)
        return definition
    
    def do_run(self, path: str, language: str, pattern: str) -> str:
        find_definition_func = None
        if language == "python":
            parser = get_parser("python")
            find_definition_func = self.find_python_definitions
        else:
            return f"ERROR: {language} is not supported, please read the file to get definitions."
        files = []
        if os.path.isfile(path):
            if not os.path.exists(path):
                return f"ERROR: File not found at {path}. Please ensure the file exists."
            files.append(path)
        else:
            # path is a directory
            full_pattern = os.path.join(path, pattern)
            files = glob.glob(full_pattern, recursive=True)
        # file -> {"classes": [], "methods": [], "functions": [], "globals": []}
        definitions = {}
        for file in files:
            with open(file, "rb") as f:
                file_content = f.read()
            tree = parser.parse(file_content)
            root_node = tree.root_node
            definitions[file] = find_definition_func(root_node)
        output = ""
        for filepath, definition in definitions.items():
            output += f"## filepath: {filepath}\n"
            if not (definition["classes"] or definition["methods"] or definition["functions"] or definition["globals"]):
                output += "No definitions found\n\n"
                continue
            if definition["classes"]:
                output += "- classes: {}\n".format(", ".join(definition["classes"]))
            if definition["methods"]:
                output += "- methods: {}\n".format(", ".join(definition["methods"]))
            if definition["functions"]:
                output += "- functions: {}\n".format(", ".join(definition["functions"]))
            if definition["globals"]:
                output += "- globals: {}\n".format(", ".join(definition["globals"]))
            output += "\n"
        if os.path.isfile(path):
            return f"Successfully list all top level source code definitions in the {path}:\n\n{output}"
        else:
            return f"Successfully list all top level source code definitions in the {path} and found {len(definitions)} files:\n\n{output}"
    