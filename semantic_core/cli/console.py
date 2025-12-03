"""Rich Console singleton для CLI.

Предоставляет единый экземпляр Console для всех команд.

Attributes:
    console: Глобальный Rich Console.

Functions:
    get_console: Получить консоль с учётом настроек.
"""

from rich.console import Console

# Глобальный Console — используется всеми командами
console = Console()


def get_console(force_terminal: bool = False, no_color: bool = False) -> Console:
    """Получить настроенную консоль.

    Args:
        force_terminal: Принудительно включить терминальный режим.
        no_color: Отключить цвета.

    Returns:
        Настроенный Rich Console.
    """
    if force_terminal or no_color:
        return Console(
            force_terminal=force_terminal,
            no_color=no_color,
        )
    return console


__all__ = ["console", "get_console"]
