"""Interactive question wizard, built with questionary."""

from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice

from . import initializr
from .config import ProjectConfig

STYLE = questionary.Style(
    [
        ("qmark", "fg:#00b894 bold"),
        ("question", "bold"),
        ("answer", "fg:#00b894 bold"),
        ("pointer", "fg:#00b894 bold"),
        ("highlighted", "fg:#00b894 bold"),
        ("selected", "fg:#00b894"),
    ]
)


def _ask(prompt):
    result = prompt.ask()
    if result is None:
        raise KeyboardInterrupt()
    return result


def run_wizard() -> ProjectConfig:
    config = ProjectConfig()

    print("Fetching current Spring Boot / Java version metadata from start.spring.io...")
    try:
        boot_version_options = initializr.list_boot_version_options()
        default_boot = initializr.default_boot_version()
        java_versions = initializr.list_java_versions()
        default_java = initializr.default_java_version()
    except Exception:
        boot_version_options, default_boot = [], ""
        java_versions, default_java = ["17", "21", "23"], "21"

    config.language = _ask(
        questionary.select(
            "Language:",
            choices=["java", "kotlin"],
            default="java",
            style=STYLE,
        )
    )

    config.build_tool = _ask(
        questionary.select(
            "Build tool:",
            choices=["maven", "gradle"],
            default="maven",
            style=STYLE,
        )
    )

    if boot_version_options:
        choices = [
            Choice(
                opt["name"] + ("  (recommended)" if opt["id"] == default_boot else ""),
                value=opt["id"],
            )
            for opt in boot_version_options
        ]
        config.boot_version = _ask(
            questionary.select(
                "Spring Boot version (RELEASE = stable; M/RC = milestone; SNAPSHOT = nightly):",
                choices=choices,
                default=next((c for c in choices if c.value == default_boot), choices[0]),
                style=STYLE,
            )
        )

    config.java_version = _ask(
        questionary.select(
            "Java version:",
            choices=java_versions,
            default=default_java if default_java in java_versions else java_versions[0],
            style=STYLE,
        )
    )

    config.group_id = _ask(
        questionary.text("Group ID:", default=config.group_id, style=STYLE)
    )
    config.artifact_id = _ask(
        questionary.text("Artifact ID:", default=config.artifact_id, style=STYLE)
    )
    config.name = config.artifact_id
    config.description = _ask(
        questionary.text("Description:", default=config.description, style=STYLE)
    )

    config.reactive = _ask(
        questionary.select(
            "Web stack:",
            choices=[
                Choice("Non-reactive (Spring MVC / Tomcat)", value=False),
                Choice("Reactive (Spring WebFlux / Netty)", value=True),
            ],
            style=STYLE,
        )
    )

    config.database = _ask(
        questionary.select(
            "Database:",
            choices=[
                Choice("PostgreSQL", value="postgresql"),
                Choice("MySQL", value="mysql"),
                Choice("MongoDB", value="mongodb"),
                Choice("H2 (in-memory)", value="h2"),
                Choice("None", value="none"),
            ],
            style=STYLE,
        )
    )

    config.caching = _ask(
        questionary.select(
            "Caching:",
            choices=[
                Choice("Redis", value="redis"),
                Choice("Caffeine (in-process)", value="caffeine"),
                Choice("None", value="none"),
            ],
            style=STYLE,
        )
    )

    extras = _ask(
        questionary.checkbox(
            "Extra features (space to toggle):",
            choices=[
                Choice("Spring Security", value="security"),
                Choice("Actuator", value="actuator"),
                Choice("Lombok (Java only)", value="lombok", disabled=(
                    "Kotlin has data classes" if config.language == "kotlin" else None
                )),
                Choice("Docker + docker-compose", value="docker"),
                Choice("GitHub Actions CI workflow", value="ci"),
            ],
            style=STYLE,
        )
    )
    config.security = "security" in extras
    config.actuator = "actuator" in extras
    config.lombok = "lombok" in extras and config.language == "java"
    config.docker = "docker" in extras
    config.ci = "ci" in extras

    output_dir = _ask(
        questionary.text(
            "Output directory (project folder will be created inside it):",
            default=".",
            style=STYLE,
        )
    )
    config.output_dir = Path(output_dir).expanduser().resolve()

    return config
