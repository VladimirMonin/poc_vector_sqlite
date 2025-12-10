"""Whisper модели для локальной транскрипции.

Классы:
    WhisperModelMLX
        Whisper для Apple Silicon (MLX/Lightning Whisper MLX).
        4-15x быстрее PyTorch MPS на M-серии чипах.

    WhisperModel
        Whisper для PyTorch (CUDA/MPS/CPU).
        Универсальная реализация для всех платформ.

Ключевое отличие от донора:
    ✅ Возвращает segments с таймкодами, а не только text!

Примеры:
    >>> from .device import get_device_info
    >>> device_type, _ = get_device_info()
    >>>
    >>> if device_type == "mlx":
    ...     model = WhisperModelMLX("large-v3-turbo")
    ... else:
    ...     model = WhisperModel("large-v3-turbo")
    >>>
    >>> model.load_model()
    >>> result = model.transcribe("audio.mp3", language="ru")
    >>> print(result["text"])  # Полный текст
    >>> print(result["segments"])  # Список сегментов с таймкодами
"""

import gc
import os
import platform
import tempfile
from pathlib import Path
from typing import Any, Optional

from .device import is_apple_silicon


class WhisperModelMLX:
    """Whisper для Apple Silicon (MLX).

    Использует:
    - mlx-whisper для large-v3-turbo (официальный Apple MLX)
    - Lightning Whisper MLX для остальных моделей

    Оптимизирован для M1/M2/M3/M4 с Neural Engine.

    Attributes:
        LIGHTNING_MODELS: Модели для Lightning Whisper MLX.
        MLX_WHISPER_MODELS: Модели для mlx-whisper.
        AVAILABLE_MODELS: Все доступные модели.

    Examples:
        >>> model = WhisperModelMLX("large-v3", batch_size=12)
        >>> model.load_model()
        >>> result = model.transcribe("audio.mp3", language="ru")
        >>> print(len(result["segments"]))  # Количество сегментов с таймкодами
    """

    LIGHTNING_MODELS = [
        "tiny",
        "small",
        "distil-small.en",
        "base",
        "medium",
        "distil-medium.en",
        "large",
        "large-v2",
        "distil-large-v2",
        "large-v3",
        "distil-large-v3",
    ]

    MLX_WHISPER_MODELS = ["large-v3-turbo"]

    AVAILABLE_MODELS = LIGHTNING_MODELS + MLX_WHISPER_MODELS

    def __init__(
        self,
        model_size: str = "large-v3",
        batch_size: int = 12,
        quantization: Optional[str] = None,
    ):
        """Инициализирует MLX Whisper модель.

        Args:
            model_size: Размер модели. Варианты:
                - "tiny", "small", "base", "medium", "large", "large-v2", "large-v3"
                - "large-v3-turbo" (самая быстрая large модель)
                - Distilled: "distil-small.en", "distil-medium.en",
                  "distil-large-v2", "distil-large-v3"
            batch_size: Размер batch для декодирования (больше = быстрее, больше RAM):
                - Tiny/Small: 16-24
                - Medium: 12-16
                - Large: 6-12
            quantization: Уровень квантизации для скорости/памяти:
                - None: Полная точность (лучшее качество)
                - "4bit": 4-bit квантизация (самая быстрая)
                - "8bit": 8-bit квантизация (баланс)

        Raises:
            RuntimeError: Если не на Apple Silicon.
            ImportError: Если lightning-whisper-mlx или mlx-whisper не установлены.
        """
        if not is_apple_silicon():
            raise RuntimeError(
                f"WhisperModelMLX requires Apple Silicon (M1/M2/M3/M4). "
                f"Current platform: {platform.system()}/{platform.machine()}"
            )

        # Выбор backend в зависимости от модели
        self.use_mlx_whisper = model_size in self.MLX_WHISPER_MODELS

        # Импорт соответствующей библиотеки
        if self.use_mlx_whisper:
            try:
                import mlx_whisper

                self.mlx_whisper_module = mlx_whisper
            except ImportError:
                raise ImportError(
                    "mlx-whisper not installed. Install with: pip install mlx-whisper"
                )
        else:
            try:
                from lightning_whisper_mlx import LightningWhisperMLX

                self.LightningWhisperMLX = LightningWhisperMLX
            except ImportError:
                raise ImportError(
                    "lightning-whisper-mlx not installed. "
                    "Install with: pip install lightning-whisper-mlx"
                )

        # Валидация модели
        if model_size not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Model '{model_size}' not available. "
                f"Choose from: {self.AVAILABLE_MODELS}"
            )

        self.model_size = model_size
        self.batch_size = batch_size
        self.quantization = quantization
        self.whisper: Optional[Any] = None

    def load_model(self, status_callback: Optional[callable] = None) -> None:
        """Загружает Whisper MLX модель.

        Args:
            status_callback: Опциональный callback для обновления статуса.

        Examples:
            >>> model = WhisperModelMLX("large-v3")
            >>> model.load_model(lambda s: print(s))
            ⏳ Загрузка Whisper MLX модели...
            ✅ Whisper MLX загружен
        """
        if self.whisper is not None:
            return

        if status_callback:
            status_callback("⏳ Загрузка Whisper MLX модели...")

        if self.use_mlx_whisper:
            # mlx-whisper загружает модель при первом transcribe()
            self.whisper = "loaded"  # Маркер
        else:
            from lightning_whisper_mlx import LightningWhisperMLX

            self.whisper = LightningWhisperMLX(
                model=self.model_size,
                batch_size=self.batch_size,
                quant=self.quantization,
            )

        if status_callback:
            status_callback("✅ Whisper MLX загружен")

    def transcribe(
        self, audio_path: str | Path, language: str = "ru"
    ) -> dict[str, Any]:
        """Транскрибирует аудиофайл в текст с сегментами.

        Args:
            audio_path: Путь к аудиофайлу (MP3, WAV, FLAC, etc.).
            language: Код языка (ru, en, es). "auto" для автоопределения.

        Returns:
            Словарь с ключами:
            - text: str - Полный транскрибированный текст
            - segments: list[dict] - Список сегментов с таймкодами:
                - start: float - Начало в секундах
                - end: float - Конец в секундах
                - text: str - Текст сегмента
            - language: str - Определённый язык

        Raises:
            RuntimeError: Если модель не загружена.

        Examples:
            >>> model = WhisperModelMLX("large-v3")
            >>> model.load_model()
            >>> result = model.transcribe("audio.mp3", language="ru")
            >>> print(result["text"])
            "Привет, это тест транскрипции."
            >>> print(result["segments"][0])
            {'start': 0.0, 'end': 2.5, 'text': 'Привет, это тест'}
        """
        if self.whisper is None:
            raise RuntimeError("Model not loaded. Call load_model() first")

        # Подготовка kwargs для транскрипции
        transcribe_kwargs = {}
        if language and language != "auto":
            transcribe_kwargs["language"] = language

        if self.use_mlx_whisper:
            # mlx-whisper API
            result = self.mlx_whisper_module.transcribe(
                str(audio_path),
                path_or_hf_repo=f"mlx-community/whisper-{self.model_size}",
                **transcribe_kwargs,
            )
        else:
            # Lightning Whisper MLX API
            result = self.whisper.transcribe(
                audio_path=str(audio_path), **transcribe_kwargs
            )

        # ✅ КЛЮЧЕВОЕ ОТЛИЧИЕ: Возвращаем полный result со segments!
        # Донор возвращал только result["text"], теряя таймкоды
        return result

    def unload_model(self) -> None:
        """Выгружает модель из памяти.

        Note:
            MLX управляет памятью автоматически, но мы можем удалить ссылку.
        """
        if self.whisper is not None:
            del self.whisper
            self.whisper = None

    def is_loaded(self) -> bool:
        """Проверяет, загружена ли модель.

        Returns:
            True если модель загружена, False в противном случае.
        """
        return self.whisper is not None


class WhisperModel:
    """Whisper для PyTorch (CUDA/MPS/CPU).

    Универсальная реализация для всех платформ через transformers.

    Examples:
        >>> model = WhisperModel("large-v3-turbo")
        >>> model.load_model()
        >>> result = model.transcribe("audio.mp3", language="russian")
        >>> print(result["text"])
        >>> print(len(result["segments"]))
    """

    def __init__(self, model_size: str = "large-v3-turbo"):
        """Инициализирует PyTorch Whisper модель.

        Args:
            model_size: Идентификатор модели из Hugging Face:
                - "large-v3-turbo" (default, самая быстрая large модель)
                - "large-v3", "large-v2", "medium", "base", "small", "tiny"
        """
        import torch

        # Определяем устройство
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            self.torch_dtype = torch.float16
        elif torch.backends.mps.is_available():
            self.device = torch.device("mps")
            self.torch_dtype = torch.float16
        else:
            self.device = torch.device("cpu")
            self.torch_dtype = torch.float32

        self.model_id = f"openai/whisper-{model_size}"
        self.model: Optional[Any] = None
        self.processor: Optional[Any] = None
        self.pipe: Optional[Any] = None

    def load_model(self, status_callback: Optional[callable] = None) -> None:
        """Загружает Whisper модель.

        Args:
            status_callback: Опциональный callback для обновления статуса.
        """
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

        if self.model is not None:
            return

        if status_callback:
            status_callback("⏳ Загрузка Whisper модели...")

        # Загрузка модели
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id,
            torch_dtype=self.torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
            attn_implementation="sdpa",
        )
        self.model.to(self.device)

        # Загрузка processor
        self.processor = AutoProcessor.from_pretrained(self.model_id)

        # ✅ КЛЮЧЕВОЕ ОТЛИЧИЕ: Включаем таймкоды!
        # Донор отключал их, чтобы избежать ошибок long-form
        self.processor.feature_extractor.return_token_timestamps = True

        # Создание pipeline
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            chunk_length_s=30,
            batch_size=16,
            return_timestamps="word",  # ✅ Включаем word-level timestamps
            torch_dtype=self.torch_dtype,
            device=self.device,
        )

        if status_callback:
            status_callback("✅ Whisper загружен")

    def transcribe(
        self, audio_path: str | Path, language: str = "russian"
    ) -> dict[str, Any]:
        """Транскрибирует аудиофайл в текст с сегментами.

        Args:
            audio_path: Путь к аудиофайлу (любой формат, поддерживаемый librosa).
            language: Язык для транскрипции (default: "russian").

        Returns:
            Словарь с ключами:
            - text: str - Полный транскрибированный текст
            - chunks: list[dict] - Список сегментов с таймкодами:
                - timestamp: tuple[float, float] - (start, end) в секундах
                - text: str - Текст сегмента

        Raises:
            RuntimeError: Если модель не загружена.

        Examples:
            >>> model = WhisperModel("large-v3-turbo")
            >>> model.load_model()
            >>> result = model.transcribe("audio.mp3")
            >>> print(result["text"])
            >>> for chunk in result["chunks"]:
            ...     start, end = chunk["timestamp"]
            ...     print(f"[{start:.1f}s - {end:.1f}s]: {chunk['text']}")
        """
        import torch

        if self.pipe is None:
            raise RuntimeError("Model not loaded. Call load_model() first")

        # Обработка аудио через librosa для универсальности
        try:
            import librosa
            import soundfile as sf

            # Загрузка аудио (любой формат) и resample до 16kHz
            audio, sr = librosa.load(str(audio_path), sr=16000, mono=True)

            # Сохранение во временный WAV файл
            fd, temp_wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)

            try:
                sf.write(temp_wav, audio, 16000)

                # Освобождение массива аудио сразу после записи
                del audio, sr

                # Транскрипция с no_grad для предотвращения накопления градиентов
                with torch.no_grad():
                    result = self.pipe(temp_wav, generate_kwargs={"language": language})

                # Освобождение result dict (может содержать tensor ссылки)
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                # ✅ КЛЮЧЕВОЕ ОТЛИЧИЕ: Возвращаем полный result с chunks!
                # chunks содержит таймкоды в формате {"timestamp": (start, end), "text": "..."}
                return result
            finally:
                # Очистка temp файла
                if os.path.exists(temp_wav):
                    os.unlink(temp_wav)

        except ImportError:
            # Fallback: прямая транскрипция (работает только для WAV)
            with torch.no_grad():
                result = self.pipe(
                    str(audio_path), generate_kwargs={"language": language}
                )

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            return result

    def unload_model(self) -> None:
        """Выгружает модель из VRAM/RAM."""
        import torch

        if self.model is not None:
            del self.model
            del self.processor
            del self.pipe
            self.model = None
            self.processor = None
            self.pipe = None

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

    def is_loaded(self) -> bool:
        """Проверяет, загружена ли модель.

        Returns:
            True если модель загружена, False в противном случае.
        """
        return self.model is not None
