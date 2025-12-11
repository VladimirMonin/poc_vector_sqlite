"""JsonReporter - экспорт snapshot в JSON формат.

Просто обёртка над SnapshotManager для консистентности API.
"""

from pathlib import Path
from typing import Optional

from semantic_core.utils.logger import get_logger
from ..models import InspectionSnapshot
from ..snapshot import SnapshotManager

logger = get_logger(__name__)


class JsonReporter:
    """JSON reporter для экспорта snapshot."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None):
        """
        Инициализация JsonReporter.

        Args:
            snapshot_manager: Менеджер снимков (опционально)
        """
        self.snapshot_manager = snapshot_manager or SnapshotManager()

    def export(
        self,
        snapshot: InspectionSnapshot,
        output_path: Path,
        compress: bool = False,
    ) -> Path:
        """
        Экспортирует snapshot в JSON.

        Args:
            snapshot: Снимок для экспорта
            output_path: Путь для сохранения
            compress: Сжимать ли (gzip)

        Returns:
            Path к сохранённому файлу
        """
        session_path = output_path.parent
        file_prefix = output_path.stem

        return self.snapshot_manager.save_snapshot(
            snapshot, session_path, file_prefix, compress=compress
        )
