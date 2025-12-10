"""Whisper локальная транскрипция для SemanticCore.

Модуль предоставляет локальную транскрипцию аудио через Whisper.
Поддерживает MLX (Apple Silicon) и PyTorch (CUDA/MPS/CPU).

Классы:
    WhisperTranscriber
        Реализация ITranscriber для локальной транскрипции.

Функции:
    get_whisper_transcriber(**kwargs) -> WhisperTranscriber
        Фабрика с понятной ошибкой при отсутствии зависимостей.

Зависимости:
    Опциональные! Установите с помощью:
    pip install semantic-core[local-whisper]

Примеры:
    >>> from semantic_core.infrastructure.local.whisper import get_whisper_transcriber
    >>>
    >>> try:
    ...     transcriber = get_whisper_transcriber(model_size="large-v3-turbo")
    ...     result = transcriber.transcribe(Path("audio.mp3"))
    ... except ImportError as e:
    ...     print(f"Whisper недоступен: {e}")

Note:
    Если зависимости не установлены, WhisperTranscriber будет None,
    а get_whisper_transcriber() вызовет понятную ImportError.
"""

from typing import Optional

# Graceful degradation: пробуем импортировать, но не падаем если нет зависимостей
WhisperTranscriber: Optional[type] = None
_import_error: Optional[str] = None

try:
    from .transcriber import WhisperTranscriber
except ImportError as e:
    _import_error = str(e)


def get_whisper_transcriber(**kwargs):
    """Фабрика для создания WhisperTranscriber с понятной ошибкой.

    Args:
        **kwargs: Аргументы для WhisperTranscriber.__init__():
            - model_size: str = "large-v3-turbo"
            - device: Optional[str] = None
            - batch_size: int = 12
            - quantization: Optional[str] = None

    Returns:
        WhisperTranscriber: Инстанс транскрайбера.

    Raises:
        ImportError: Если зависимости не установлены.

    Examples:
        >>> transcriber = get_whisper_transcriber(
        ...     model_size="large-v3-turbo",
        ...     device="mlx",
        ...     quantization="4bit"
        ... )
        >>> result = transcriber.transcribe(Path("audio.mp3"))
    """
    if WhisperTranscriber is None:
        raise ImportError(
            "Whisper dependencies not installed.\n"
            "\n"
            "Install with:\n"
            "  pip install semantic-core[local-whisper]\n"
            "\n"
            "This will install:\n"
            "  - lightning-whisper-mlx (Apple Silicon)\n"
            "  - mlx-whisper (Apple Silicon)\n"
            "  - transformers + torch (PyTorch)\n"
            "  - librosa + soundfile (audio processing)\n"
            "\n"
            f"Original error: {_import_error}"
        )

    return WhisperTranscriber(**kwargs)


__all__ = ["WhisperTranscriber", "get_whisper_transcriber"]
