"""WhisperTranscriber - локальная транскрипция через Whisper.

Классы:
    WhisperTranscriber
        Реализация ITranscriber для локальной транскрипции.
        Поддерживает MLX (Apple Silicon) и PyTorch (CUDA/MPS/CPU).

Примеры:
    >>> from semantic_core.infrastructure.local.whisper import WhisperTranscriber
    >>>
    >>> # Auto-detection устройства
    >>> transcriber = WhisperTranscriber(model_size="large-v3-turbo")
    >>> result = transcriber.transcribe(Path("audio.mp3"))
    >>> print(result.full_text)
    >>> for segment in result.segments:
    ...     print(f"[{segment.start_seconds:.1f}s]: {segment.text}")
    >>>
    >>> # Принудительный выбор устройства
    >>> transcriber = WhisperTranscriber(device="cuda")  # Только NVIDIA GPU
    >>> transcriber = WhisperTranscriber(device="mlx")   # Только Apple Silicon
"""

from pathlib import Path
from typing import Optional

from semantic_core.interfaces.transcriber import (
    ITranscriber,
    TranscriptionResult,
    TranscriptionSegment,
)

from .device import get_device_info
from .models import WhisperModel, WhisperModelMLX


class WhisperTranscriber(ITranscriber):
    """Локальная транскрипция через Whisper (MLX/PyTorch).

    Автоматически выбирает оптимальный backend:
    - MLX для Apple Silicon (4-15x быстрее PyTorch)
    - CUDA для NVIDIA GPU
    - MPS для Apple Silicon fallback
    - CPU для всех остальных

    Attributes:
        _model_size: Размер модели Whisper.
        _device_type: Тип устройства (mlx, cuda, mps, cpu).
        _batch_size: Размер batch для декодирования.
        _quantization: Уровень квантизации (4bit, 8bit, None).
        _whisper: Инстанс модели (lazy loaded).

    Examples:
        >>> transcriber = WhisperTranscriber("large-v3-turbo")
        >>> result = transcriber.transcribe(Path("audio.mp3"), language="ru")
        >>> print(f"Язык: {result.language}")
        >>> print(f"Текст: {result.full_text}")
        >>> print(f"Сегментов: {len(result.segments)}")
    """

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: Optional[str] = None,
        batch_size: int = 12,
        quantization: Optional[str] = None,
    ):
        """Инициализирует WhisperTranscriber.

        Args:
            model_size: Размер модели Whisper:
                - "large-v3-turbo" (default, самая быстрая large модель)
                - "large-v3", "large-v2", "medium", "base", "small", "tiny"
                - Distilled (только MLX): "distil-large-v3", "distil-medium.en"
            device: Принудительный выбор устройства:
                - None: автоопределение (рекомендуется)
                - "mlx": только Apple Silicon MLX
                - "cuda": только NVIDIA GPU
                - "mps": только Apple Silicon MPS
                - "cpu": только CPU
            batch_size: Размер batch для декодирования (больше = быстрее, больше RAM):
                - Tiny/Small: 16-24
                - Medium: 12-16
                - Large: 6-12
            quantization: Уровень квантизации (только MLX):
                - None: полная точность (default)
                - "4bit": 4-bit квантизация (самая быстрая)
                - "8bit": 8-bit квантизация (баланс)

        Examples:
            >>> # Auto-detection (рекомендуется)
            >>> transcriber = WhisperTranscriber()
            >>>
            >>> # Принудительный MLX
            >>> transcriber = WhisperTranscriber(device="mlx", quantization="4bit")
            >>>
            >>> # Принудительный CUDA
            >>> transcriber = WhisperTranscriber(device="cuda", model_size="medium")
        """
        self._model_size = model_size
        self._device_type = device or self._auto_detect_device()
        self._batch_size = batch_size
        self._quantization = quantization
        self._whisper: Optional[WhisperModel | WhisperModelMLX] = None

    def _auto_detect_device(self) -> str:
        """Автоопределение оптимального устройства.

        Returns:
            Тип устройства: "mlx", "cuda", "mps", "cpu".
        """
        device_type, _ = get_device_info()
        return device_type

    def _ensure_loaded(self) -> None:
        """Ленивая загрузка модели при первом вызове.

        Raises:
            RuntimeError: Если устройство не поддерживается.
            ImportError: Если отсутствуют необходимые зависимости.
        """
        if self._whisper is not None:
            return

        if self._device_type == "mlx":
            self._whisper = WhisperModelMLX(
                model_size=self._model_size,
                batch_size=self._batch_size,
                quantization=self._quantization,
            )
        else:
            self._whisper = WhisperModel(model_size=self._model_size)

        self._whisper.load_model()

    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Транскрибирует аудиофайл с таймкодами.

        Args:
            audio_path: Путь к аудиофайлу (mp3, wav, flac, m4a, ogg, webm).
            language: Код языка (ru, en, es, etc.). None = автоопределение.

        Returns:
            TranscriptionResult с полным текстом и сегментами с таймкодами.

        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: Если формат не поддерживается.
            RuntimeError: Если транскрипция не удалась.

        Examples:
            >>> transcriber = WhisperTranscriber()
            >>> result = transcriber.transcribe(Path("audio.mp3"), language="ru")
            >>> print(result.full_text)
            "Привет, это тест транскрипции."
            >>>
            >>> for seg in result.segments:
            ...     print(f"[{seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s]: {seg.text}")
            [0.0s - 2.5s]: Привет, это тест
            [2.5s - 5.0s]: транскрипции.
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Проверка формата
        if audio_path.suffix.lower().lstrip(".") not in self.supported_formats:
            raise ValueError(
                f"Unsupported audio format: {audio_path.suffix}. "
                f"Supported: {self.supported_formats}"
            )

        # Ленивая загрузка модели
        self._ensure_loaded()

        # Транскрипция через модель
        raw_result = self._whisper.transcribe(
            str(audio_path), language=language or "auto"
        )

        # Преобразование в унифицированный DTO
        return self._convert_to_dto(raw_result)

    def _convert_to_dto(self, raw_result: dict) -> TranscriptionResult:
        """Преобразует результат Whisper в TranscriptionResult DTO.

        Args:
            raw_result: Сырой результат от Whisper модели.

        Returns:
            TranscriptionResult с унифицированным форматом.

        Note:
            MLX и PyTorch возвращают разные форматы сегментов:
            - MLX: {"segments": [{"start": float, "end": float, "text": str}]}
            - PyTorch: {"chunks": [{"timestamp": (start, end), "text": str}]}
        """
        full_text = raw_result.get("text", "").strip()
        language = raw_result.get("language")

        segments: list[TranscriptionSegment] = []

        # MLX формат (segments с start/end)
        if "segments" in raw_result:
            for seg in raw_result["segments"]:
                segments.append(
                    TranscriptionSegment(
                        text=seg["text"].strip(),
                        start_seconds=seg["start"],
                        end_seconds=seg["end"],
                        confidence=None,  # MLX не предоставляет confidence
                    )
                )

        # PyTorch формат (chunks с timestamp tuple)
        elif "chunks" in raw_result:
            for chunk in raw_result["chunks"]:
                timestamp = chunk.get("timestamp")
                if timestamp and len(timestamp) == 2:
                    start, end = timestamp
                    segments.append(
                        TranscriptionSegment(
                            text=chunk["text"].strip(),
                            start_seconds=start,
                            end_seconds=end if end is not None else start + 1.0,
                            confidence=None,  # PyTorch не предоставляет confidence
                        )
                    )

        return TranscriptionResult(
            full_text=full_text,
            segments=segments,
            language=language,
            duration_seconds=segments[-1].end_seconds if segments else None,
        )

    @property
    def supported_formats(self) -> list[str]:
        """Поддерживаемые форматы аудио.

        Returns:
            Список расширений файлов без точки.
        """
        return ["mp3", "wav", "flac", "m4a", "ogg", "webm"]
