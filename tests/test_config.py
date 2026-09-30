"""Unit tests for ProjectConfig."""

from pathlib import Path

from spring_cli.config import ProjectConfig


def test_defaults():
    cfg = ProjectConfig()
    assert cfg.language == "java"
    assert cfg.build_tool == "maven"
    assert cfg.database == "none"
    assert cfg.caching == "none"
    assert cfg.reactive is False


def test_resolved_package_name_defaults_to_group_id():
    cfg = ProjectConfig(group_id="com.acme")
    assert cfg.resolved_package_name() == "com.acme"


def test_resolved_package_name_explicit_override():
    cfg = ProjectConfig(group_id="com.acme", package_name="com.acme.custom")
    assert cfg.resolved_package_name() == "com.acme.custom"


def test_project_path_joins_output_dir_and_artifact_id():
    cfg = ProjectConfig(artifact_id="myapp", output_dir=Path("/tmp/out"))
    assert cfg.project_path() == Path("/tmp/out") / "myapp"
