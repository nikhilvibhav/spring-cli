"""Generates a GitHub Actions CI workflow for the scaffolded project."""

from __future__ import annotations

from ..config import ProjectConfig

_MAVEN_WORKFLOW = """name: CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up JDK {java_version}
        uses: actions/setup-java@v4
        with:
          java-version: '{java_version}'
          distribution: 'temurin'
          cache: maven
      - name: Build with Maven
        run: ./mvnw -B verify
"""

_GRADLE_WORKFLOW = """name: CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up JDK {java_version}
        uses: actions/setup-java@v4
        with:
          java-version: '{java_version}'
          distribution: 'temurin'
          cache: gradle
      - name: Build with Gradle
        run: ./gradlew build
"""


_DOCKER_JOB = """
  docker:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Build image (layer-cached via GitHub Actions cache)
        uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: {artifact_id}:ci
          # GitHub Actions runners are ephemeral, so without this the Docker
          # build cache (dependency-download layer, jarmode extraction, etc.)
          # would be discarded every run. type=gha persists it in the repo's
          # Actions cache (~10GB, evicted after 7 days unused) instead.
          cache-from: type=gha
          cache-to: type=gha,mode=max
"""


def apply(config: ProjectConfig) -> None:
    if not config.ci:
        return

    template = _MAVEN_WORKFLOW if config.build_tool == "maven" else _GRADLE_WORKFLOW
    content = template.format(java_version=config.java_version)
    if config.docker:
        content += _DOCKER_JOB.format(artifact_id=config.artifact_id)

    workflow_dir = config.project_path() / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "ci.yml").write_text(content, encoding="utf-8")
