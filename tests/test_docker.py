"""Unit tests for spring_cli.features.docker."""

from pathlib import Path

from spring_cli.config import ProjectConfig
from spring_cli.features import docker


def test_apply_noop_when_docker_disabled(tmp_path):
    cfg = ProjectConfig(artifact_id="app", docker=False, output_dir=tmp_path)
    cfg.project_path().mkdir(parents=True)
    docker.apply(cfg)
    assert not (cfg.project_path() / "Dockerfile").exists()
    assert not (cfg.project_path() / "docker-compose.yml").exists()


def test_dockerfile_uses_alpine_images_and_layered_jarmode():
    cfg = ProjectConfig(build_tool="maven", java_version="21")
    content = docker._dockerfile(cfg)
    assert "eclipse-temurin:21-jdk-alpine" in content
    assert "eclipse-temurin:21-jre-alpine" in content
    assert "jarmode=tools" in content
    assert "extract --layers" in content
    # Each extracted layer directory should be copied independently for cache reuse.
    assert "extracted/dependencies/" in content
    assert "extracted/spring-boot-loader/" in content
    assert "extracted/snapshot-dependencies/" in content
    assert "extracted/application/" in content


def test_dockerfile_sets_java_opts_entrypoint():
    cfg = ProjectConfig(build_tool="gradle", java_version="17")
    content = docker._dockerfile(cfg)
    assert "JAVA_OPTS" in content
    assert "-Xmx512m" in content
    assert 'ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar application.jar"]' in content


def test_dockerfile_maven_vs_gradle_build_commands():
    maven_content = docker._dockerfile(ProjectConfig(build_tool="maven"))
    gradle_content = docker._dockerfile(ProjectConfig(build_tool="gradle"))
    assert "mvnw" in maven_content and "target/*.jar" in maven_content
    assert "gradlew" in gradle_content and "build/libs/*.jar" in gradle_content


def test_docker_compose_includes_matching_db_and_cache_services(tmp_path):
    cfg = ProjectConfig(
        artifact_id="myapp", database="postgresql", caching="redis",
        docker=True, output_dir=tmp_path,
    )
    cfg.project_path().mkdir(parents=True)
    docker.apply(cfg)
    compose = (cfg.project_path() / "docker-compose.yml").read_text()
    assert "postgres:" in compose
    assert "POSTGRES_DB: myapp" in compose
    assert "redis:" in compose
    assert "app:" in compose


def test_docker_compose_no_extra_services_when_no_db_or_cache(tmp_path):
    cfg = ProjectConfig(
        artifact_id="myapp", database="none", caching="none",
        docker=True, output_dir=tmp_path,
    )
    cfg.project_path().mkdir(parents=True)
    docker.apply(cfg)
    compose = (cfg.project_path() / "docker-compose.yml").read_text()
    assert "postgres:" not in compose
    assert "redis:" not in compose
    assert "app:" in compose
