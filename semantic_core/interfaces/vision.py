"""Интерфейс для анализа изображений.

Классы:
    IVisionAnalyzer
        ABC для провайдеров анализа изображений (Gemini Vision, Local VLM).

DTO:
    VisionResult
        Результат анализа изображения.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VisionResult:
    """Результат анализа изображения.

    Attributes:
        description: Детальное описание содержимого изображения.
        alt_text: Короткий alt-текст для accessibility.
        keywords: Список ключевых слов/тегов.
        ocr_text: Извлечённый текст (OCR), если есть.
    """

    description: str
    alt_text: str
    keywords: list[str]
    ocr_text: Optional[str] = None


class IVisionAnalyzer(ABC):
    """Интерфейс для анализа изображений.

    Унифицирует работу с разными провайдерами:
    - Gemini Vision API (cloud)
    - LLaVA (local)
    - Qwen-VL (local)
    - GPT-4 Vision (cloud)
    - etc.
    """

    @abstractmethod
    def analyze(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
    ) -> VisionResult:
        """Анализирует изображение.

        Args:
            image_path: Путь к изображению (jpg, png, webp, etc.).
            prompt: Кастомный промпт для анализа. None = дефолтный промпт.

        Returns:
            VisionResult с описанием и метаданными.

        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: Если формат не поддерживается.
            RuntimeError: Если анализ не удался.

        Note:
            Дефолтный промпт должен генерировать:
            - description: детальное описание (2-3 предложения)
            - alt_text: краткий alt-текст (1 предложение)
            - keywords: 5-10 релевантных тегов
            - ocr_text: текст если есть на изображении
        """
        raise NotImplementedError

    @property
    def supported_formats(self) -> list[str]:
        """Поддерживаемые форматы изображений.

        Returns:
            Список расширений (без точки): ['jpg', 'png', 'webp', ...].

        Note:
            Базовый набор: jpg, jpeg, png, webp, gif.
            Конкретные провайдеры могут расширять список.
        """
        return ["jpg", "jpeg", "png", "webp", "gif"]
