from pathlib import Path
from prompt_loader import PromptLoader

PromptLoader(prompt_dir=Path(__file__).parent / "prompt")

__all__ = [
    "PromptLoader"
]