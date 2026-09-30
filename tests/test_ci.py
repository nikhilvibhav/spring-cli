"""Unit tests for spring_cli.features.ci."""

import yaml

from spring_cli.config import ProjectConfig
from spring_cli.features import ci


def test_apply_noop_when_ci_disabled(tmp_path):
    cfg = ProjectConfig(ci=False, output_dir=tmp_path, artifact_id="app")
    cfg.project_path().mkdir(parents=True)
    ci.apply(cfg)
    assert not (cfg.project_path() / ".github" / "workflows" / "ci.yml").exists()


def test_maven_workflow_without_docker_job(tmp_path):
    cfg = ProjectConfig(
        build_tool="maven", java_version="21", ci=True, docker=False,
        artifact_id="app", output_dir=tmp_path,
    )
    cfg.project_path().mkdir(parents=True)
    ci.apply(cfg)
    text = (cfg.project_path() / ".github" / "workflows" / "ci.yml").read_text()
    parsed = yaml.safe_load(text)
    assert set(parsed["jobs"].keys()) == {"build"}
    assert "mvnw" in text


def test_gradle_workflow_with_docker_job(tmp_path):
    cfg = ProjectConfig(
        build_tool="gradle", java_version="21", ci=True, docker=True,
        artifact_id="myapp", output_dir=tmp_path,
    )
    cfg.project_path().mkdir(parents=True)
    ci.apply(cfg)
    text = (cfg.project_path() / ".github" / "workflows" / "ci.yml").read_text()
    parsed = yaml.safe_load(text)
    assert set(parsed["jobs"].keys()) == {"build", "docker"}
    assert parsed["jobs"]["docker"]["needs"] == "build"
    assert "gradlew" in text
    # Docker build should use the GitHub Actions cache backend, not per-run cache.
    assert "type=gha" in text
    assert "myapp:ci" in text
