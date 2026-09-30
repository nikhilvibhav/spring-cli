"""Generates a Dockerfile and docker-compose.yml for the scaffolded project."""

from __future__ import annotations

from ..config import ProjectConfig

_JAVA_OPTS = (
    "-Xms256m -Xmx512m -XX:MaxRAMPercentage=75.0 "
    "-XX:+ExitOnOutOfMemoryError -Djava.security.egd=file:/dev/./urandom"
)

# Both templates use Spring Boot's own "jarmode=tools" layer extraction
# (the same mechanism the Spring Boot Maven/Gradle plugin's layered-jar
# support is built on: https://docs.spring.io/spring-boot/reference/packaging/container-images/dockerfiles.html)
# so each COPY becomes its own Docker layer (dependencies rarely change,
# application code changes often), giving much faster incremental rebuilds
# than copying one monolithic fat jar. No pom.xml/build.gradle changes are
# needed: layered jars are produced by default by the Spring Boot plugin.
_MAVEN_DOCKERFILE = """# syntax=docker/dockerfile:1
FROM eclipse-temurin:{java_version}-jdk-alpine AS build
WORKDIR /app
COPY mvnw .
COPY .mvn .mvn
COPY pom.xml .
RUN chmod +x mvnw && ./mvnw -B dependency:go-offline
COPY src src
RUN ./mvnw -B package -DskipTests
RUN cp target/*.jar application.jar \\
    && java -Djarmode=tools -jar application.jar extract --layers --destination extracted

FROM eclipse-temurin:{java_version}-jre-alpine
WORKDIR /application
COPY --from=build /app/extracted/dependencies/ ./
COPY --from=build /app/extracted/spring-boot-loader/ ./
COPY --from=build /app/extracted/snapshot-dependencies/ ./
COPY --from=build /app/extracted/application/ ./
EXPOSE 8080
ENV JAVA_OPTS="{java_opts}"
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar application.jar"]
"""

_GRADLE_DOCKERFILE = """# syntax=docker/dockerfile:1
FROM eclipse-temurin:{java_version}-jdk-alpine AS build
WORKDIR /app
COPY gradlew .
COPY gradle gradle
COPY build.gradle* settings.gradle* .
RUN chmod +x gradlew && ./gradlew dependencies --no-daemon || true
COPY src src
RUN ./gradlew build -x test --no-daemon
RUN cp build/libs/*.jar application.jar \\
    && java -Djarmode=tools -jar application.jar extract --layers --destination extracted

FROM eclipse-temurin:{java_version}-jre-alpine
WORKDIR /application
COPY --from=build /app/extracted/dependencies/ ./
COPY --from=build /app/extracted/spring-boot-loader/ ./
COPY --from=build /app/extracted/snapshot-dependencies/ ./
COPY --from=build /app/extracted/application/ ./
EXPOSE 8080
ENV JAVA_OPTS="{java_opts}"
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar application.jar"]
"""

_DB_SERVICES = {
    "postgresql": (
        "  postgres:\n"
        "    image: postgres:16\n"
        "    environment:\n"
        "      POSTGRES_DB: {name}\n"
        "      POSTGRES_USER: postgres\n"
        "      POSTGRES_PASSWORD: postgres\n"
        "    ports:\n"
        "      - \"5432:5432\"\n"
        "    volumes:\n"
        "      - postgres-data:/var/lib/postgresql/data\n"
    ),
    "mysql": (
        "  mysql:\n"
        "    image: mysql:8\n"
        "    environment:\n"
        "      MYSQL_DATABASE: {name}\n"
        "      MYSQL_ROOT_PASSWORD: root\n"
        "    ports:\n"
        "      - \"3306:3306\"\n"
        "    volumes:\n"
        "      - mysql-data:/var/lib/mysql\n"
    ),
    "mongodb": (
        "  mongodb:\n"
        "    image: mongo:7\n"
        "    environment:\n"
        "      MONGO_INITDB_DATABASE: {name}\n"
        "    ports:\n"
        "      - \"27017:27017\"\n"
        "    volumes:\n"
        "      - mongo-data:/data/db\n"
    ),
}

_REDIS_SERVICE = (
    "  redis:\n"
    "    image: redis:7-alpine\n"
    "    ports:\n"
    "      - \"6379:6379\"\n"
)

_VOLUMES = {
    "postgresql": "  postgres-data:\n",
    "mysql": "  mysql-data:\n",
    "mongodb": "  mongo-data:\n",
}


def _dockerfile(config: ProjectConfig) -> str:
    template = _MAVEN_DOCKERFILE if config.build_tool == "maven" else _GRADLE_DOCKERFILE
    return template.format(java_version=config.java_version, java_opts=_JAVA_OPTS)


def _docker_compose(config: ProjectConfig) -> str:
    services = ""
    volumes = ""

    if config.database in _DB_SERVICES:
        services += _DB_SERVICES[config.database].format(name=config.artifact_id)
        volumes += _VOLUMES[config.database]
    if config.caching == "redis":
        services += _REDIS_SERVICE

    app_service = (
        "  app:\n"
        "    build: .\n"
        "    ports:\n"
        "      - \"8080:8080\"\n"
    )
    dependency_names = _dependency_names(config)
    if dependency_names:
        app_service += "    depends_on:\n" + "".join(f"      - {d}\n" for d in dependency_names)

    content = "services:\n" + app_service + services
    if volumes:
        content += "\nvolumes:\n" + volumes
    return content


def _dependency_names(config: ProjectConfig) -> list[str]:
    names = []
    if config.database == "postgresql":
        names.append("postgres")
    elif config.database == "mysql":
        names.append("mysql")
    elif config.database == "mongodb":
        names.append("mongodb")
    if config.caching == "redis":
        names.append("redis")
    return names


def apply(config: ProjectConfig) -> None:
    if not config.docker:
        return

    project_path = config.project_path()
    (project_path / "Dockerfile").write_text(_dockerfile(config), encoding="utf-8")
    (project_path / "docker-compose.yml").write_text(_docker_compose(config), encoding="utf-8")
