from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ModelEntry:
    name: str
    description: str
    url: str
    pull_count: int
    tag_count: int
    updated_text: str
    updated_timestamp: Optional[datetime]
    capabilities: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    is_cloud: bool = False


@dataclass
class ModelTag:
    model_name: str
    tag: str
    size_gb: Optional[float] = None
    context_window: Optional[int] = None
    modalities: list[str] = field(default_factory=list)
    is_latest: bool = False
    is_mlx: bool = False
