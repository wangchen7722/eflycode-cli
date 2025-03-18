from pathlib import Path
from echo.prompt.prompt_loader import PromptLoader

PromptLoader(prompt_dir=Path(__file__).parent / "prompts")

__all__ = [
    "PromptLoader"
]