"""Команды настроек.

Команды:
    ModelCommand — /model [name]
    ContextCommand — /context [N]
"""

from rich.panel import Panel

from semantic_core.cli.chat.slash.base import BaseSlashCommand, SlashResult
from semantic_core.cli.chat.slash.handler import ChatContext


class ModelCommand(BaseSlashCommand):
    """Показать или сменить модель LLM."""

    name = "model"
    description = "Показать или сменить модель LLM"
    aliases = ["m"]
    usage = "/model [название_модели]"

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать или сменить модель."""
        if not args.strip():
            # Показываем текущую модель
            ctx.console.print(
                f"Текущая модель: [cyan]{ctx.llm.model_name}[/cyan]"
            )
            ctx.console.print(
                "[dim]Для смены: /model <название>[/dim]\n"
                "[dim]Примеры: gemini-2.0-flash, gemini-1.5-pro[/dim]"
            )
            return SlashResult()

        new_model = args.strip()

        # Пробуем создать новый провайдер с другой моделью
        try:
            from semantic_core.infrastructure.llm import GeminiLLMProvider

            # Проверяем, что это GeminiLLMProvider
            if not isinstance(ctx.llm, GeminiLLMProvider):
                ctx.console.print(
                    "[yellow]Смена модели поддерживается только для Gemini[/yellow]"
                )
                return SlashResult()

            # Создаём новый провайдер с новой моделью
            new_llm = GeminiLLMProvider(
                api_key=ctx.llm._api_key,  # type: ignore
                model=new_model,
            )

            # Обновляем контекст и RAG
            old_model = ctx.llm.model_name
            ctx.llm = new_llm
            ctx.rag._llm = new_llm

            ctx.console.print(
                f"[green]✓ Модель изменена: {old_model} → {new_model}[/green]"
            )

        except Exception as e:
            ctx.console.print(f"[red]Ошибка смены модели: {e}[/red]")

        return SlashResult()


class ContextCommand(BaseSlashCommand):
    """Изменить количество чанков контекста."""

    name = "context"
    description = "Показать или изменить количество чанков контекста"
    aliases = ["ctx"]
    usage = "/context [N]"

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать или изменить количество чанков."""
        if not args.strip():
            # Показываем текущее значение
            ctx.console.print(
                f"Чанков контекста: [cyan]{ctx.context_chunks}[/cyan]"
            )
            ctx.console.print(
                "[dim]Для изменения: /context <число> (1-20)[/dim]"
            )
            return SlashResult()

        # Парсим число
        try:
            new_value = int(args.strip())
        except ValueError:
            ctx.console.print(f"[red]Неверное число: {args}[/red]")
            return SlashResult()

        if new_value < 1 or new_value > 20:
            ctx.console.print("[red]Число должно быть от 1 до 20[/red]")
            return SlashResult()

        old_value = ctx.context_chunks
        ctx.context_chunks = new_value
        ctx.rag._context_chunks = new_value

        ctx.console.print(
            f"[green]✓ Чанков контекста: {old_value} → {new_value}[/green]"
        )
        return SlashResult()


class TemperatureCommand(BaseSlashCommand):
    """Изменить температуру генерации."""

    name = "temperature"
    description = "Показать или изменить температуру генерации"
    aliases = ["temp"]
    usage = "/temperature [0.0-2.0]"

    def execute(self, ctx: ChatContext, args: str) -> SlashResult:
        """Показать или изменить температуру."""
        if not args.strip():
            ctx.console.print(
                f"Температура: [cyan]{ctx.temperature}[/cyan]"
            )
            ctx.console.print(
                "[dim]Для изменения: /temperature <0.0-2.0>[/dim]"
            )
            return SlashResult()

        try:
            new_value = float(args.strip())
        except ValueError:
            ctx.console.print(f"[red]Неверное значение: {args}[/red]")
            return SlashResult()

        if new_value < 0.0 or new_value > 2.0:
            ctx.console.print("[red]Значение должно быть от 0.0 до 2.0[/red]")
            return SlashResult()

        old_value = ctx.temperature
        ctx.temperature = new_value

        ctx.console.print(
            f"[green]✓ Температура: {old_value} → {new_value}[/green]"
        )
        return SlashResult()


__all__ = ["ModelCommand", "ContextCommand", "TemperatureCommand"]
