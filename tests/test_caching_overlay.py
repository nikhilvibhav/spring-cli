"""Unit tests for spring_cli.features.caching_overlay (Caffeine injection)."""

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

from spring_cli.config import ProjectConfig
from spring_cli.features import caching_overlay


def _prep(tmp_path, **kwargs) -> ProjectConfig:
    cfg = ProjectConfig(artifact_id="myapp", output_dir=tmp_path, **kwargs)
    cfg.project_path().mkdir(parents=True)
    return cfg


def test_noop_when_not_caffeine(tmp_path):
    cfg = _prep(tmp_path, caching="redis", build_tool="gradle")
    (cfg.project_path() / "build.gradle").write_text("dependencies {\n}\n", encoding="utf-8")
    caching_overlay.apply(cfg)
    assert not (cfg.project_path() / "gradle" / "libs.versions.toml").exists()


def test_maven_injects_dependency_directly(tmp_path):
    cfg = _prep(tmp_path, caching="caffeine", build_tool="maven")
    pom = cfg.project_path() / "pom.xml"
    pom.write_text("<project>\n    <dependencies>\n    </dependencies>\n</project>\n", encoding="utf-8")
    caching_overlay.apply(cfg)
    text = pom.read_text(encoding="utf-8")
    assert "com.github.ben-manes.caffeine" in text
    assert "<artifactId>caffeine</artifactId>" in text
    # Maven has no version-catalog equivalent.
    assert not (cfg.project_path() / "gradle" / "libs.versions.toml").exists()


def test_gradle_groovy_uses_version_catalog(tmp_path):
    cfg = _prep(tmp_path, caching="caffeine", build_tool="gradle")
    (cfg.project_path() / "build.gradle").write_text("dependencies {\n}\n", encoding="utf-8")
    caching_overlay.apply(cfg)

    catalog_path = cfg.project_path() / "gradle" / "libs.versions.toml"
    assert catalog_path.exists()
    catalog = tomllib.loads(catalog_path.read_text(encoding="utf-8"))
    assert catalog["versions"]["caffeine"] == caching_overlay.CAFFEINE_VERSION
    assert catalog["libraries"]["caffeine"]["module"] == caching_overlay.CAFFEINE_MODULE

    build_text = (cfg.project_path() / "build.gradle").read_text(encoding="utf-8")
    assert "implementation libs.caffeine" in build_text


def test_gradle_kotlin_dsl_uses_version_catalog(tmp_path):
    cfg = _prep(tmp_path, caching="caffeine", build_tool="gradle", language="kotlin")
    (cfg.project_path() / "build.gradle.kts").write_text("dependencies {\n}\n", encoding="utf-8")
    caching_overlay.apply(cfg)

    catalog_path = cfg.project_path() / "gradle" / "libs.versions.toml"
    assert catalog_path.exists()

    build_text = (cfg.project_path() / "build.gradle.kts").read_text(encoding="utf-8")
    assert "implementation(libs.caffeine)" in build_text


def test_catalog_entry_not_duplicated_on_repeat_apply(tmp_path):
    cfg = _prep(tmp_path, caching="caffeine", build_tool="gradle")
    (cfg.project_path() / "build.gradle").write_text("dependencies {\n}\n", encoding="utf-8")
    caching_overlay.apply(cfg)
    catalog_path = cfg.project_path() / "gradle" / "libs.versions.toml"
    first_pass = catalog_path.read_text(encoding="utf-8")

    caching_overlay.apply(cfg)
    second_pass = catalog_path.read_text(encoding="utf-8")
    assert first_pass == second_pass
