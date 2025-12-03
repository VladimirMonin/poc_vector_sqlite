"""Прогресс-индикаторы для CLI.

Контекстные менеджеры для спиннеров и прогресс-баров.
"""

from contextlib import contextmanager
from typing import Iterator, Optional

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)


console = Console()


@contextmanager
def progress_spinner(message: str = "Обработка...") -> Iterator[None]:
    """Контекстный менеджер для спиннера.

    Args:
        message: Сообщение рядом со спиннером.

    Yields:
        None

    Example:
        with progress_spinner("Загрузка..."):
            do_something_slow()
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description=f"[cyan]{message}[/cyan]", total=None)
        yield


@contextmanager
def progress_bar(
    total: int,
    description: str = "Обработка...",
    show_time: bool = True,
) -> Iterator[Progress]:
    """Контекстный менеджер для прогресс-бара.

    Args:
        total: Общее количество элементов.
        description: Описание задачи.
        show_time: Показывать прошедшее время.

    Yields:
        Progress объект с методом advance() для обновления.

    Example:
        with progress_bar(100, "Индексация") as progress:
            for item in items:
                process(item)
                progress.advance(task_id)
    """
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ]

    if show_time:
        columns.append(TimeElapsedColumn())

    with Progress(*columns, console=console) as progress:
        task_id = progress.add_task(
            description=f"[cyan]{description}[/cyan]",
            total=total,
        )
        # Добавляем task_id как атрибут для удобства
        progress.current_task_id = task_id  # type: ignore
        yield progress


class ProgressTracker:
    """Трекер прогресса с обновлением статуса.

    Обёртка над Rich Progress для более удобного API.

    Example:
        tracker = ProgressTracker(total=100, description="Обработка")
        with tracker:
            for item in items:
                tracker.update(status=f"Файл: {item.name}")
                process(item)
                tracker.advance()
    """

    def __init__(
        self,
        total: int,
        description: str = "Обработка...",
        show_time: bool = True,
    ):
        """Инициализация трекера.

        Args:
            total: Общее количество элементов.
            description: Описание задачи.
            show_time: Показывать прошедшее время.
        """
        self.total = total
        self.description = description
        self.show_time = show_time
        self._progress: Optional[Progress] = None
        self._task_id: Optional[int] = None

    def __enter__(self) -> "ProgressTracker":
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ]

        if self.show_time:
            columns.append(TimeElapsedColumn())

        self._progress = Progress(*columns, console=console)
        self._progress.start()
        self._task_id = self._progress.add_task(
            description=f"[cyan]{self.description}[/cyan]",
            total=self.total,
        )
        return self

    def __exit__(self, *args) -> None:
        if self._progress:
            self._progress.stop()

    def advance(self, amount: int = 1) -> None:
        """Продвинуть прогресс.

        Args:
            amount: На сколько продвинуть (по умолчанию 1).
        """
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, advance=amount)

    def update(self, status: Optional[str] = None) -> None:
        """Обновить статус задачи.

        Args:
            status: Новое описание задачи.
        """
        if self._progress and self._task_id is not None and status:
            self._progress.update(
                self._task_id,
                description=f"[cyan]{status}[/cyan]",
            )
