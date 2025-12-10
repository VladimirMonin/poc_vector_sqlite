"""SnapshotManager - сохранение и загрузка инспекционных артефактов.

Управляет:
- Сохранением снимков в JSON
- Загрузкой снимков из файлов
- Организацией папок артефактов
- Версионированием формата данных
"""

import json
import gzip
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import asdict

from semantic_core.utils.logger import get_logger
from .models import InspectionSnapshot, ProviderMetadata, ChunkInspection

logger = get_logger(__name__)


class SnapshotManager:
    """Менеджер для сохранения/загрузки snapshot артефактов."""

    def __init__(self, artifacts_root: Optional[Path] = None):
        """
        Инициализация SnapshotManager.

        Args:
            artifacts_root: Корневая папка для артефактов.
                           По умолчанию: ./inspection_artifacts/
        """
        if artifacts_root is None:
            artifacts_root = Path.cwd() / "inspection_artifacts"

        self.artifacts_root = Path(artifacts_root)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

        logger.trace(
            "snapshot_manager_initialized", artifacts_root=str(self.artifacts_root)
        )

    def create_session_folder(self, session_name: Optional[str] = None) -> Path:
        """
        Создаёт папку для сессии инспекции.

        Args:
            session_name: Имя сессии. По умолчанию: timestamp

        Returns:
            Path к папке сессии
        """
        if session_name is None:
            session_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        session_path = self.artifacts_root / session_name
        session_path.mkdir(parents=True, exist_ok=True)

        logger.debug("session_folder_created", session_path=str(session_path))
        return session_path

    def save_snapshot(
        self,
        snapshot: InspectionSnapshot,
        session_path: Path,
        file_prefix: str,
        compress: bool = False,
    ) -> Path:
        """
        Сохраняет InspectionSnapshot в JSON.

        Args:
            snapshot: Снимок для сохранения
            session_path: Путь к папке сессии
            file_prefix: Префикс имени файла (example_md)
            compress: Сжимать ли файл (gzip)

        Returns:
            Path к сохранённому файлу
        """
        # Конвертируем dataclass в dict
        data = self._snapshot_to_dict(snapshot)

        # Определяем имя файла
        suffix = ".json.gz" if compress else ".json"
        filename = f"{file_prefix}_inspection{suffix}"
        filepath = session_path / filename

        # Сохраняем
        if compress:
            with gzip.open(filepath, "wt", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        file_size = filepath.stat().st_size
        logger.info(
            "snapshot_saved",
            filepath=str(filepath),
            size_bytes=file_size,
            compressed=compress,
        )

        return filepath

    def load_snapshot(self, filepath: Path) -> InspectionSnapshot:
        """
        Загружает InspectionSnapshot из JSON.

        Args:
            filepath: Путь к файлу снимка

        Returns:
            Восстановленный InspectionSnapshot
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Snapshot file not found: {filepath}")

        # Определяем сжатие
        is_compressed = filepath.suffix == ".gz"

        # Загружаем
        if is_compressed:
            with gzip.open(filepath, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

        logger.debug("snapshot_loaded", filepath=str(filepath))

        # Конвертируем обратно в dataclass
        return self._dict_to_snapshot(data)

    def _snapshot_to_dict(self, snapshot: InspectionSnapshot) -> dict:
        """Конвертирует InspectionSnapshot в сериализуемый dict."""
        data = asdict(snapshot)

        # Обрабатываем datetime
        if snapshot.processing_timestamp:
            data["processing_timestamp"] = snapshot.processing_timestamp.isoformat()

        # Обрабатываем Path
        if snapshot.config_toml_path:
            data["config_toml_path"] = str(snapshot.config_toml_path)

        return data

    def _dict_to_snapshot(self, data: dict) -> InspectionSnapshot:
        """Конвертирует dict обратно в InspectionSnapshot."""
        # Восстанавливаем datetime
        if data.get("processing_timestamp"):
            data["processing_timestamp"] = datetime.fromisoformat(
                data["processing_timestamp"]
            )

        # Восстанавливаем Path
        if data.get("config_toml_path"):
            data["config_toml_path"] = Path(data["config_toml_path"])

        # Восстанавливаем ProviderMetadata
        if data.get("embedder_metadata"):
            data["embedder_metadata"] = ProviderMetadata(**data["embedder_metadata"])

        if data.get("llm_metadata"):
            data["llm_metadata"] = ProviderMetadata(**data["llm_metadata"])

        if data.get("transcriber_metadata"):
            data["transcriber_metadata"] = ProviderMetadata(
                **data["transcriber_metadata"]
            )

        # Восстанавливаем ChunkInspection
        if data.get("chunks"):
            data["chunks"] = [ChunkInspection(**chunk) for chunk in data["chunks"]]

        # MediaInspection и SearchInspection оставляем как dict
        # (они не имеют сложной вложенности)

        return InspectionSnapshot(**data)

    def list_sessions(self) -> list[Path]:
        """
        Возвращает список всех папок сессий.

        Returns:
            Список путей к папкам сессий (отсортированы по дате)
        """
        sessions = [d for d in self.artifacts_root.iterdir() if d.is_dir()]
        sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return sessions

    def list_snapshots(self, session_path: Path) -> list[Path]:
        """
        Возвращает список всех снимков в сессии.

        Args:
            session_path: Путь к папке сессии

        Returns:
            Список путей к JSON файлам снимков
        """
        snapshots = list(session_path.glob("*_inspection.json*"))
        snapshots.sort()
        return snapshots
