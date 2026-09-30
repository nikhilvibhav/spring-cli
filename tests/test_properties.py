"""Unit tests for spring_cli.features.properties (datasource/cache config)."""

from spring_cli.config import ProjectConfig
from spring_cli.features import properties


def _read(cfg: ProjectConfig) -> str:
    properties.apply(cfg)
    props_path = cfg.project_path() / "src" / "main" / "resources" / "application.properties"
    return props_path.read_text(encoding="utf-8") if props_path.exists() else ""


def _prep(tmp_path, **kwargs):
    kwargs.setdefault("artifact_id", "myapp")
    cfg = ProjectConfig(output_dir=tmp_path, **kwargs)
    (cfg.project_path() / "src" / "main" / "resources").mkdir(parents=True)
    return cfg


def test_noop_when_no_db_or_cache(tmp_path):
    cfg = _prep(tmp_path, database="none", caching="none")
    assert _read(cfg) == ""


def test_postgresql_non_reactive_jdbc(tmp_path):
    cfg = _prep(tmp_path, database="postgresql", reactive=False)
    text = _read(cfg)
    assert "spring.datasource.url=jdbc:postgresql://localhost:5432/myapp" in text
    assert "spring.datasource.username=postgres" in text
    assert "spring.datasource.password=postgres" in text
    assert "spring.jpa.hibernate.ddl-auto=update" in text


def test_postgresql_reactive_r2dbc(tmp_path):
    cfg = _prep(tmp_path, database="postgresql", reactive=True)
    text = _read(cfg)
    assert "spring.r2dbc.url=r2dbc:postgresql://localhost:5432/myapp" in text
    assert "spring.r2dbc.password=postgres" in text
    assert "spring.jpa" not in text


def test_mongodb_uses_data_mongodb_uri_regardless_of_reactive(tmp_path):
    for reactive in (True, False):
        cfg = _prep(tmp_path, database="mongodb", reactive=reactive, artifact_id=f"m{reactive}")
        text = _read(cfg)
        assert f"spring.data.mongodb.uri=mongodb://localhost:27017/m{reactive}" in text


def test_redis_caching_properties(tmp_path):
    cfg = _prep(tmp_path, caching="redis")
    text = _read(cfg)
    assert "spring.cache.type=redis" in text
    assert "spring.data.redis.port=6379" in text


def test_caffeine_caching_properties(tmp_path):
    cfg = _prep(tmp_path, caching="caffeine")
    text = _read(cfg)
    assert "spring.cache.type=caffeine" in text
