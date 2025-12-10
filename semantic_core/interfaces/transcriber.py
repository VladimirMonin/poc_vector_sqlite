"""Интерфейс для транскрибации аудио.

Классы:
    ITranscriber
        ABC для провайдеров транскрипции (Gemini Audio, Whisper).

DTO:
    TranscriptionSegment
        Сегмент транскрипции с таймкодами.
    TranscriptionResult
        Результат транскрипции от любого провайдера.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TranscriptionSegment:
    """Сегмент транскрипции с таймкодами.

    Attributes:
        text: Текст сегмента.
        start_seconds: Начало сегмента в секундах.
        end_seconds: Конец сегмента в секундах.
        confidence: Уверенность модели (0.0-1.0), если доступна.
    """

    text: str
    start_seconds: float
    end_seconds: float
    confidence: Optional[float] = None


@dataclass
class TranscriptionResult:
    """Результат транскрипции от любого провайдера.

    Attributes:
        full_text: Полный текст транскрипции.
        segments: Список сегментов с таймкодами (может быть пустым).
        language: Определённый язык (ISO 639-1: ru, en, etc.).
        duration_seconds: Длительность аудио в секундах.
    """

    full_text: str
    segments: list[TranscriptionSegment]
    language: Optional[str] = None
    duration_seconds: Optional[float] = None

    @property
    def has_timestamps(self) -> bool:
        """Проверяет наличие таймкодов в сегментах.

        Returns:
            True если есть хотя бы один сегмент с таймкодами.
        """
        return len(self.segments) > 0 and self.segments[0].start_seconds is not None


class ITranscriber(ABC):
    """Интерфейс для транскрипции аудио.

    Унифицирует работу с разными провайдерами:
    - Gemini Audio API (cloud)
    - Whisper (local MLX/PyTorch)
    - AssemblyAI (cloud)
    - etc.
    """

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Транскрибирует аудиофайл.

        Args:
            audio_path: Путь к аудиофайлу (mp3, wav, flac, etc.).
            language: Код языка (ru, en, auto). None = автоопределение.

        Returns:
            TranscriptionResult с текстом и опциональными сегментами.

        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: Если формат не поддерживается.
            RuntimeError: Если транскрипция не удалась.

        Note:
            Разные провайдеры возвращают разное качество сегментации:
            - Gemini: обычно без таймкодов (segments пустой)
            - Whisper: детальные сегменты с точными таймкодами
        """
        raise NotImplementedError

    @property
    def supported_formats(self) -> list[str]:
        """Поддерживаемые форматы аудио.

        Returns:
            Список расширений (без точки): ['mp3', 'wav', 'flac', ...].

        Note:
            Базовый набор: mp3, wav, flac, m4a, ogg.
            Конкретные провайдеры могут расширять список.
        """
        return ["mp3", "wav", "flac", "m4a", "ogg"]
