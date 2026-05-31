import typer

app = typer.Typer(
    name="photonfeed",
    help="Multi-agent personalized photonics research feed.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Photonfeed CLI."""


@app.command()
def version() -> None:
    """Print the photonfeed version."""
    from photonfeed import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
