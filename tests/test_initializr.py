"""Unit tests for spring_cli.initializr's pure logic (no network calls)."""

import pytest

from spring_cli.config import ProjectConfig
from spring_cli.initializr import (
    _is_stable,
    _project_type,
    _to_maven_coordinate,
    resolve_dependencies,
)


@pytest.mark.parametrize(
    "version_id,expected",
    [
        ("4.1.1.RELEASE", True),
        ("4.2.0.M2", False),
        ("4.1.2.BUILD-SNAPSHOT", False),
        ("4.0.8.RELEASE", True),
    ],
)
def test_is_stable(version_id, expected):
    assert _is_stable(version_id) is expected


@pytest.mark.parametrize(
    "version_id,expected",
    [
        ("4.1.1.RELEASE", "4.1.1"),
        ("4.0.8.RELEASE", "4.0.8"),
        ("4.2.0.M2", "4.2.0.M2"),
        ("4.1.2.BUILD-SNAPSHOT", "4.1.2.BUILD-SNAPSHOT"),
    ],
)
def test_to_maven_coordinate_strips_release_suffix_only(version_id, expected):
    assert _to_maven_coordinate(version_id) == expected


@pytest.mark.parametrize(
    "build_tool,language,expected",
    [
        ("maven", "java", "maven-project"),
        ("maven", "kotlin", "maven-project"),
        ("gradle", "java", "gradle-project"),
        ("gradle", "kotlin", "gradle-project-kotlin"),
    ],
)
def test_project_type(build_tool, language, expected):
    cfg = ProjectConfig(build_tool=build_tool, language=language)
    assert _project_type(cfg) == expected


def test_resolve_dependencies_non_reactive_no_extras():
    cfg = ProjectConfig(reactive=False, database="none", caching="none")
    assert resolve_dependencies(cfg) == ["web"]


def test_resolve_dependencies_reactive_web():
    cfg = ProjectConfig(reactive=True)
    assert resolve_dependencies(cfg)[0] == "webflux"


def test_resolve_dependencies_postgres_non_reactive_uses_jpa():
    cfg = ProjectConfig(reactive=False, database="postgresql")
    deps = resolve_dependencies(cfg)
    assert "postgresql" in deps
    assert "data-jpa" in deps
    assert "data-r2dbc" not in deps


def test_resolve_dependencies_postgres_reactive_uses_r2dbc():
    cfg = ProjectConfig(reactive=True, database="postgresql")
    deps = resolve_dependencies(cfg)
    assert "postgresql" in deps
    assert "data-r2dbc" in deps
    assert "data-jpa" not in deps


def test_resolve_dependencies_mongodb_reactive_vs_non_reactive():
    non_reactive = resolve_dependencies(ProjectConfig(reactive=False, database="mongodb"))
    reactive = resolve_dependencies(ProjectConfig(reactive=True, database="mongodb"))
    assert "data-mongodb" in non_reactive
    assert "data-mongodb-reactive" in reactive


def test_resolve_dependencies_redis_caching_adds_cache_starter():
    deps = resolve_dependencies(ProjectConfig(caching="redis"))
    assert "data-redis" in deps
    assert "cache" in deps


def test_resolve_dependencies_caffeine_only_adds_generic_cache_starter():
    deps = resolve_dependencies(ProjectConfig(caching="caffeine"))
    assert "cache" in deps
    # No Initializr id for Caffeine itself; that's added as a build overlay.
    assert not any("caffeine" in d for d in deps)


def test_resolve_dependencies_extras():
    cfg = ProjectConfig(security=True, actuator=True, lombok=True, language="java")
    deps = resolve_dependencies(cfg)
    assert "security" in deps
    assert "actuator" in deps
    assert "lombok" in deps


def test_resolve_dependencies_lombok_skipped_for_kotlin():
    cfg = ProjectConfig(language="kotlin", lombok=True)
    deps = resolve_dependencies(cfg)
    assert "lombok" not in deps


def test_resolve_dependencies_no_duplicates():
    # Redis caching + reactive both touch redis; ensure de-dup keeps order stable.
    cfg = ProjectConfig(reactive=True, caching="redis", database="postgresql")
    deps = resolve_dependencies(cfg)
    assert len(deps) == len(set(deps))
