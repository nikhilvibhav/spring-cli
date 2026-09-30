"""Injects the Caffeine dependency into the generated pom.xml / build.gradle.

Spring Initializr has no dedicated "Caffeine" dependency id; only the generic
"Spring Cache Abstraction" (cache) starter. When the user picks Caffeine as
the cache provider we add the actual library ourselves.

For Gradle projects the version is declared once in the Gradle version
catalog (gradle/libs.versions.toml) and referenced from build.gradle(.kts)
via the type-safe `libs.caffeine` accessor, matching modern Gradle
convention. Maven has no equivalent catalog mechanism, so the pom.xml
dependency is added directly and left unmanaged (resolved from Spring Boot's
dependency-management BOM).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import ProjectConfig

CAFFEINE_MODULE = "com.github.ben-manes.caffeine:caffeine"
CAFFEINE_VERSION = "3.3.0"
CAFFEINE_ALIAS = "caffeine"

_MAVEN_DEP = (
    "        <dependency>\n"
    "            <groupId>com.github.ben-manes.caffeine</groupId>\n"
    "            <artifactId>caffeine</artifactId>\n"
    "        </dependency>\n"
)


def _apply_maven(project_path: Path) -> None:
    pom = project_path / "pom.xml"
    if not pom.exists():
        return
    text = pom.read_text(encoding="utf-8")
    text = re.sub(r"(</dependencies>)", _MAVEN_DEP + r"\1", text, count=1)
    pom.write_text(text, encoding="utf-8")


def _ensure_catalog_entry(project_path: Path, alias: str, module: str, version: str) -> None:
    """Add (or update) a [versions]/[libraries] pair in gradle/libs.versions.toml."""
    catalog_path = project_path / "gradle" / "libs.versions.toml"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    text = catalog_path.read_text(encoding="utf-8") if catalog_path.exists() else ""

    if re.search(rf'^{re.escape(alias)}\s*=', text, flags=re.MULTILINE):
        return  # already declared, nothing to do

    if "[versions]" not in text:
        text = "[versions]\n" + text
    text = re.sub(r"(\[versions\]\s*\n)", rf'\1{alias} = "{version}"\n', text, count=1)

    lib_line = f'{alias} = {{ module = "{module}", version.ref = "{alias}" }}\n'
    if "[libraries]" in text:
        text = re.sub(r"(\[libraries\]\s*\n)", r"\1" + lib_line, text, count=1)
    else:
        text += "\n[libraries]\n" + lib_line

    catalog_path.write_text(text, encoding="utf-8")


def _apply_gradle(project_path: Path, is_kotlin_dsl: bool) -> None:
    build_file = project_path / ("build.gradle.kts" if is_kotlin_dsl else "build.gradle")
    if not build_file.exists():
        return

    _ensure_catalog_entry(project_path, CAFFEINE_ALIAS, CAFFEINE_MODULE, CAFFEINE_VERSION)

    text = build_file.read_text(encoding="utf-8")
    addition = (
        f"\timplementation(libs.{CAFFEINE_ALIAS})\n"
        if is_kotlin_dsl
        else f"\timplementation libs.{CAFFEINE_ALIAS}\n"
    )
    text = re.sub(r"(dependencies\s*\{)", r"\1\n" + addition.rstrip("\n"), text, count=1)
    build_file.write_text(text, encoding="utf-8")


def apply(config: ProjectConfig) -> None:
    if config.caching != "caffeine":
        return

    project_path = config.project_path()
    if config.build_tool == "maven":
        _apply_maven(project_path)
    else:
        is_kotlin_dsl = (project_path / "build.gradle.kts").exists()
        _apply_gradle(project_path, is_kotlin_dsl)
