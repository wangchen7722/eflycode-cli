from pathlib import Path
from .prompt_loader import PromptLoader

PromptLoader(prompt_dir=Path(__file__).parent / "prompts")

__all__ = [
    "PromptLoader"
]