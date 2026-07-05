from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def banner() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]Speech To Text[/bold cyan]\n"
            "Faster Whisper CLI",
            border_style="cyan",
        )
    )


def show_config(cfg) -> None:

    table = Table(show_header=False)

    table.add_column(style="cyan")
    table.add_column()

    table.add_row("Modelo", cfg.model)
    table.add_row("Idioma", cfg.language)
    table.add_row("Salida", str(cfg.output))
    table.add_row("Formatos", ", ".join(cfg.formats))

    console.print(table)


def info(message: str):

    console.print(f"[green]✓[/green] {message}")


def error(message: str):

    console.print(f"[red]✗[/red] {message}")
