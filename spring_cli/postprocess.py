"""Runs all post-Initializr feature generators in order."""

from __future__ import annotations

from .config import ProjectConfig
from .features import caching_overlay, ci, docker, properties


def apply_all(config: ProjectConfig) -> None:
    properties.apply(config)
    caching_overlay.apply(config)
    docker.apply(config)
    ci.apply(config)
