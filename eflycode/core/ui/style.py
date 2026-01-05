from typing import Mapping, Optional, Dict

_DEFAULT_STYPES: Dict[str, str] = {
    "composer.prompt": "bold",
    "composer.placeholder": "italic",

    "composer.toolbar": "#5A5A5A bold",

    "select.title": "bold",
    "select.option": "",
    "select.option.selected": "reverse bold",
    "select.option.disabled": "italic",
    "select.option.description": "italic",
    "select.option.description.disabled": "italic",
}


def build_prompt_toolkit_style(overrides: Optional[Mapping[str, str]] = None):
    from prompt_toolkit.styles import Style
    merged = dict(_DEFAULT_STYPES)
    if overrides:
        merged.update(dict(overrides))

    return Style.from_dict(merged)