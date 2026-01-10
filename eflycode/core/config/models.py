"""配置模型（Pydantic）"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from eflycode.core.constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    DEFAULT_SYSTEM_VERSION,
)
from eflycode.core.context.strategies import (
    ContextStrategyConfig,
    SLIDING_WINDOW_SIZE,
    SUMMARY_KEEP_RECENT,
    SUMMARY_THRESHOLD,
)
from eflycode.core.llm.protocol import LLMConfig


class ModelEntry(BaseModel):
    model: str
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    max_context_length: Optional[int] = None


class ModelSection(BaseModel):
    default: Optional[str] = None
    entries: List[ModelEntry] = Field(default_factory=list)


class SummaryConfig(BaseModel):
    threshold: float = SUMMARY_THRESHOLD
    keep_recent: int = SUMMARY_KEEP_RECENT
    model: Optional[str] = None


class SlidingWindowConfig(BaseModel):
    size: int = SLIDING_WINDOW_SIZE


class ContextSection(BaseModel):
    strategy: Literal["summary", "sliding_window"] = "summary"
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    sliding_window: SlidingWindowConfig = Field(default_factory=SlidingWindowConfig)


class CheckpointingSection(BaseModel):
    enabled: bool = False


class WorkspaceSection(BaseModel):
    workspace_dir: Optional[str] = None
    settings_dir: Optional[str] = None
    settings_file: Optional[str] = None


class ConfigMeta(BaseModel):
    workspace_dir: Path
    config_file_path: Optional[Path] = None
    source: Literal["user", "project", "default"] = "default"
    system_version: str = DEFAULT_SYSTEM_VERSION


class Config(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    model: ModelSection = Field(default_factory=ModelSection)
    context: Optional[ContextSection] = None
    checkpointing: Optional[CheckpointingSection] = None
    workspace: Optional[Union[WorkspaceSection, str]] = None
    meta: ConfigMeta

    @property
    def model_name(self) -> str:
        if self.model.default:
            return self.model.default
        if self.model.entries:
            return self.model.entries[0].model
        return DEFAULT_MODEL

    @property
    def model_display_name(self) -> str:
        entry = self.get_current_model_entry()
        return entry.name if entry and entry.name else self.model_name

    @property
    def llm_config(self) -> LLMConfig:
        entry = self.get_current_model_entry()
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("EFLYCODE_API_KEY")
        if entry and entry.api_key:
            api_key = entry.api_key or api_key
        return LLMConfig(
            model=self.model_name,
            name=self.model_display_name,
            api_key=api_key,
            base_url=entry.base_url if entry else None,
            timeout=entry.timeout if entry else DEFAULT_TIMEOUT,
            max_retries=entry.max_retries if entry else DEFAULT_MAX_RETRIES,
            temperature=entry.temperature if entry else None,
            max_tokens=entry.max_tokens if entry else None,
        )

    @property
    def context_config(self) -> Optional[ContextStrategyConfig]:
        if not self.context:
            return None
        return ContextStrategyConfig(
            strategy_type=self.context.strategy,
            summary_threshold=self.context.summary.threshold,
            summary_keep_recent=self.context.summary.keep_recent,
            summary_model=self.context.summary.model,
            sliding_window_size=self.context.sliding_window.size,
        )

    @property
    def workspace_dir(self) -> Path:
        return self.meta.workspace_dir

    @property
    def config_file_path(self) -> Optional[Path]:
        return self.meta.config_file_path

    @property
    def checkpointing_enabled(self) -> bool:
        return bool(self.checkpointing and self.checkpointing.enabled)

    @property
    def source(self) -> str:
        return self.meta.source

    @property
    def system_version(self) -> str:
        return self.meta.system_version

    def get_current_model_entry(self) -> Optional[ModelEntry]:
        if not self.model.entries:
            return None
        target = self.model_name
        for entry in self.model.entries:
            if entry.model == target:
                return entry
        return self.model.entries[0]
