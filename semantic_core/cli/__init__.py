"""Semantic Core CLI — Command Line Interface.

Entry point для CLI приложения.

Functions:
    main: Точка входа CLI.

Example:
    $ semantic --help
    $ semantic init
    $ semantic config show
    $ semantic doctor
"""

from semantic_core.cli.app import app


def main() -> None:
    """Точка входа для CLI."""
    app()


__all__ = ["main", "app"]
