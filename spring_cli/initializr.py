"""Client for the start.spring.io Initializr REST API."""

from __future__ import annotations

import io
import zipfile
from typing import Any, Dict, List, Optional

import requests

from .config import ProjectConfig

BASE_URL = "https://start.spring.io"
METADATA_URL = f"{BASE_URL}/metadata/client"
STARTER_URL = f"{BASE_URL}/starter.zip"

_metadata_cache: Optional[Dict[str, Any]] = None


def get_metadata() -> Dict[str, Any]:
    """Fetch (and cache) the Initializr capability metadata.

    Used to discover current default/available Spring Boot & Java versions
    without hardcoding values that go stale.
    """
    global _metadata_cache
    if _metadata_cache is None:
        resp = requests.get(METADATA_URL, headers={"Accept": "application/json"}, timeout=15)
        resp.raise_for_status()
        _metadata_cache = resp.json()
    return _metadata_cache


def _is_stable(version_id: str) -> bool:
    """RELEASE-suffixed ids are the only ones Maven Central always has fully
    synced; SNAPSHOT/M/RC builds are pre-releases and more prone to broken
    BOM resolution on start.spring.io."""
    return version_id.endswith(".RELEASE")


def list_boot_versions(stable_only: bool = True) -> List[str]:
    meta = get_metadata()
    values = meta.get("bootVersion", {}).get("values", [])
    ids = [v["id"] for v in values]
    if stable_only:
        stable = [i for i in ids if _is_stable(i)]
        if stable:
            return stable
    return ids


def default_boot_version() -> str:
    """Newest stable (RELEASE) version, falling back to the Initializr
    default if nothing looks stable."""
    stable = list_boot_versions(stable_only=True)
    if stable:
        return stable[0]
    meta = get_metadata()
    return meta.get("bootVersion", {}).get("default", "")


def list_boot_version_options() -> List[Dict[str, str]]:
    """Full list of selectable Spring Boot versions (stable RELEASEs plus
    milestone/RC/SNAPSHOT builds), each as {"id", "name"}, in the order
    start.spring.io presents them (newest first)."""
    meta = get_metadata()
    return meta.get("bootVersion", {}).get("values", [])


def list_java_versions() -> List[str]:
    meta = get_metadata()
    values = meta.get("javaVersion", {}).get("values", [])
    return [v["id"] for v in values]


def default_java_version() -> str:
    meta = get_metadata()
    return meta.get("javaVersion", {}).get("default", "21")


def resolve_dependencies(config: ProjectConfig) -> List[str]:
    """Translate wizard choices into Initializr dependency ids."""
    deps: List[str] = []

    # Web stack
    deps.append("webflux" if config.reactive else "web")

    # Database
    if config.database == "postgresql":
        deps.append("postgresql")
        deps.append("data-r2dbc" if config.reactive else "data-jpa")
    elif config.database == "mysql":
        deps.append("mysql")
        deps.append("data-r2dbc" if config.reactive else "data-jpa")
    elif config.database == "h2":
        deps.append("h2")
        deps.append("data-r2dbc" if config.reactive else "data-jpa")
    elif config.database == "mongodb":
        deps.append("data-mongodb-reactive" if config.reactive else "data-mongodb")
    # "none" -> no dependency

    # Caching
    if config.caching == "redis":
        deps.append("data-redis-reactive" if config.reactive else "data-redis")
        deps.append("cache")
    elif config.caching == "caffeine":
        # Initializr has no dedicated Caffeine id; the "cache" starter is added
        # and the Caffeine library itself is injected as a build-file overlay.
        deps.append("cache")

    if config.security:
        deps.append("security")
    if config.actuator:
        deps.append("actuator")
    if config.lombok and config.language == "java":
        deps.append("lombok")

    # De-duplicate while preserving order
    seen = set()
    ordered = []
    for d in deps:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    return ordered


def _project_type(config: ProjectConfig) -> str:
    if config.build_tool == "gradle":
        return "gradle-project-kotlin" if config.language == "kotlin" else "gradle-project"
    return "maven-project"


def _to_maven_coordinate(version_id: str) -> str:
    """Initializr's metadata ids use a legacy "x.y.z.RELEASE" display form for
    GA releases, but the actual published Maven artifact version is just
    "x.y.z" (no RELEASE suffix). Passing the RELEASE-suffixed form through
    verbatim causes BOM resolution to fail server-side for some project types
    (observed with Kotlin+Gradle). SNAPSHOT/M/RC suffixes ARE part of the real
    coordinate and must be kept as-is."""
    if version_id.endswith(".RELEASE"):
        return version_id[: -len(".RELEASE")]
    return version_id


def _base_params(config: ProjectConfig, dependencies: List[str]) -> Dict[str, str]:
    return {
        "type": _project_type(config),
        "language": config.language,
        "packaging": config.packaging,
        "javaVersion": config.java_version,
        "groupId": config.group_id,
        "artifactId": config.artifact_id,
        "name": config.name,
        "description": config.description,
        "packageName": config.resolved_package_name(),
        "dependencies": ",".join(dependencies),
    }


def _fetch_zip_bytes(params: Dict[str, str]) -> bytes:
    """Call starter.zip and return the zip bytes, or raise a RuntimeError with
    a readable message. start.spring.io returns a Spring "Whitelabel Error
    Page" (HTML, with the real HTTP status) when it can't resolve the
    requested Spring Boot BOM, so we validate both status and content-type."""
    resp = requests.get(STARTER_URL, params=params, timeout=60)
    content_type = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or "zip" not in content_type:
        snippet = resp.text[:300].replace("\n", " ") if resp.text else ""
        raise RuntimeError(
            f"start.spring.io returned HTTP {resp.status_code} ({content_type or 'unknown type'}) "
            f"for bootVersion={params.get('bootVersion', '<default>')}: {snippet}"
        )
    return resp.content


def download_and_extract(config: ProjectConfig, dependencies: List[str]) -> None:
    """Call start.spring.io/starter.zip and extract the archive into config.project_path().

    If the requested Spring Boot version fails to resolve server-side (a real,
    observed start.spring.io failure mode), automatically retries with other
    stable release versions before giving up.
    """
    params = _base_params(config, dependencies)

    # Order: 1) the user's exact request, 2) omit bootVersion entirely (lets
    # start.spring.io apply its own internal default — this reliably works
    # even when explicitly passing that very same version fails, which is an
    # observed start.spring.io quirk especially for Kotlin+Gradle), 3) other
    # stable release versions as a last resort.
    candidates: List[Optional[str]] = [config.boot_version or None, None]
    try:
        for v in list_boot_versions(stable_only=True):
            if v not in candidates:
                candidates.append(v)
    except Exception:
        pass
    # de-duplicate while preserving order
    seen_candidates = []
    for c in candidates:
        if c not in seen_candidates:
            seen_candidates.append(c)
    candidates = seen_candidates

    errors: List[str] = []
    zip_bytes: Optional[bytes] = None
    used_version: Optional[str] = config.boot_version or None

    for version in candidates:
        attempt_params = dict(params)
        if version:
            attempt_params["bootVersion"] = _to_maven_coordinate(version)
        else:
            attempt_params.pop("bootVersion", None)
        try:
            zip_bytes = _fetch_zip_bytes(attempt_params)
            used_version = version
            break
        except (RuntimeError, requests.RequestException) as exc:
            errors.append(str(exc))
            continue

    if zip_bytes is None:
        raise RuntimeError(
            "Could not generate a project from start.spring.io after trying "
            f"{len(candidates)} Spring Boot version(s):\n- " + "\n- ".join(errors)
        )

    if used_version != (config.boot_version or None):
        config.boot_version = used_version or ""

    # start.spring.io's zip has no wrapping folder (pom.xml/build.gradle sit
    # at the archive root), so extract straight into the project directory.
    project_path = config.project_path()
    project_path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(project_path)
