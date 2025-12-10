"""Модели данных для Observatory.

Определяет структуру данных для инспекции pipeline:
- ChunkInspection: Данные о чанке
- MediaInspection: Данные о медиа-обработке
- SearchInspection: Данные о поиске
- ProviderMetadata: Информация о провайдере
- InspectionSnapshot: Полный снимок обработки
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from pathlib import Path


@dataclass
class ProviderMetadata:
    """Метаданные провайдера для multi-provider inspection."""

    provider_type: str  # GeminiEmbedder, MLXEmbedder, OpenAIEmbedder, etc.
    model_name: Optional[str] = None
    dimension: Optional[int] = None
    max_tokens: Optional[int] = None
    device: Optional[str] = None  # CPU/GPU/Metal/Apple Neural Engine
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkInspection:
    """Полная информация о чанке для инспекции."""

    chunk_id: int
    chunk_type: str
    content: str
    headers: list[str]
    language: Optional[str]
    size: int
    context_text: str
    embedding_preview: Optional[list[float]] = None
    embedding_dimension: int = 0


@dataclass
class MediaInspection:
    """Полная информация об обработке медиа."""

    asset_path: str
    asset_absolute_path: str
    media_type: str  # image/audio/video
    file_size_bytes: int
    surrounding_text_before: str
    surrounding_text_after: str
    system_prompt: str
    user_prompt: str
    model_name: str
    response_raw: Optional[dict]
    response_parsed: Optional[Any]  # MediaAnalysisResult
    final_chunk_content: str
    processing_time_ms: float


@dataclass
class SearchInspection:
    """Полная информация о поисковом запросе."""

    query: str
    search_mode: str  # vector/exact/hybrid
    limit: int
    query_vector_preview: list[float]
    query_vector_dimension: int
    results: list[dict]
    results_count: int
    search_time_ms: float


@dataclass
class InspectionSnapshot:
    """Полный снимок обработки документа.

    Сохраняется в JSON для:
    - Сравнения между запусками
    - A/B тестирования провайдеров
    - Регрессионного тестирования
    - Ручного анализа artifacts (input file, similarity matrix, etc.)
    """

    snapshot_version: str = "1.0"  # Версионирование формата
    file_path: str = ""
    file_content: str = ""  # Полное содержимое входного файла
    file_content_preview: str = ""
    processing_timestamp: Optional[datetime] = None
    total_duration_ms: float = 0.0

    # Метаданные провайдеров
    embedder_metadata: Optional[ProviderMetadata] = None
    llm_metadata: Optional[ProviderMetadata] = None
    transcriber_metadata: Optional[ProviderMetadata] = None

    # Конфигурация
    config_hash: Optional[str] = None
    config_toml_path: Optional[Path] = None

    # Данные обработки
    chunks: list[ChunkInspection] = field(default_factory=list)
    media: list[MediaInspection] = field(default_factory=list)
    searches: list[SearchInspection] = field(default_factory=list)

    # Метрики производительности
    steps: list[dict[str, Any]] = field(default_factory=list)
