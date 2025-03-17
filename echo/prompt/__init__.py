from pathlib import Path
from prompt_loader import PromptLoader

prompt_loader = PromptLoader(prompt_dir=Path(__file__).parent / "prompt")

__all__ = [
    "prompt_loader"
]