"""spring-cli entry point."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import initializr, postprocess
from .wizard import run_wizard

console = Console()


def _summary_table(config, dependencies) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("Language", config.language)
    table.add_row("Build tool", config.build_tool)
    table.add_row("Spring Boot", config.boot_version or "(Initializr default)")
    table.add_row("Java version", config.java_version)
    table.add_row("Web stack", "Reactive (WebFlux)" if config.reactive else "Non-reactive (MVC)")
    table.add_row("Database", config.database)
    table.add_row("Caching", config.caching)
    table.add_row("Security", "yes" if config.security else "no")
    table.add_row("Actuator", "yes" if config.actuator else "no")
    table.add_row("Lombok", "yes" if config.lombok else "no")
    table.add_row("Docker", "yes" if config.docker else "no")
    table.add_row("CI workflow", "yes" if config.ci else "no")
    table.add_row("Dependencies", ", ".join(dependencies))
    table.add_row("Output path", str(config.project_path()))
    return table


def main() -> int:
    console.print(Panel.fit("spring-cli — Spring Boot project scaffolder", style="bold green"))

    try:
        config = run_wizard()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        return 1

    dependencies = initializr.resolve_dependencies(config)

    console.print()
    console.print(Panel(_summary_table(config, dependencies), title="Project summary"))

    proceed = True
    try:
        import questionary

        proceed = questionary.confirm("Generate the project?", default=True).ask()
    except Exception:
        pass
    if not proceed:
        console.print("[yellow]Cancelled.[/yellow]")
        return 1

    console.print("\n[bold]Requesting base project from start.spring.io...[/bold]")
    requested_boot_version = config.boot_version
    try:
        initializr.download_and_extract(config, dependencies)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to generate project from start.spring.io: {exc}[/red]")
        return 1

    if requested_boot_version and config.boot_version != requested_boot_version:
        used = config.boot_version or "start.spring.io's own default"
        console.print(
            f"[yellow]Spring Boot {requested_boot_version} failed to resolve on start.spring.io; "
            f"used {used} instead.[/yellow]"
        )

    console.print("[bold]Applying scaffold overlays (DB/cache config, Docker, CI)...[/bold]")
    postprocess.apply_all(config)

    console.print(
        Panel.fit(
            f"[green]Project created at {config.project_path()}[/green]",
            title="Done",
        )
    )
    if config.build_tool == "maven":
        console.print("Next steps: cd into the project and run [bold]./mvnw spring-boot:run[/bold]")
    else:
        console.print("Next steps: cd into the project and run [bold]./gradlew bootRun[/bold]")
    if config.docker:
        console.print("Start dependencies with [bold]docker compose up -d[/bold] before running the app.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
