"""CLI команды.

Модули:
    init_cmd: semantic init — инициализация проекта.
    config_cmd: semantic config — управление конфигурацией.
    doctor_cmd: semantic doctor — диагностика.
"""

from semantic_core.cli.commands import init_cmd
from semantic_core.cli.commands import config_cmd
from semantic_core.cli.commands import doctor_cmd

__all__ = ["init_cmd", "config_cmd", "doctor_cmd"]
