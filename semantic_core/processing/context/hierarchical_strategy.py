"""Иерархическая стратегия формирования контекста.

Классы:
    HierarchicalContextStrategy
        Формирует обогащенный контекст с учетом структуры документа.
"""

from semantic_core.domain import Chunk, ChunkType, Document, MEDIA_CHUNK_TYPES
from semantic_core.interfaces.context import BaseContextStrategy
from semantic_core.utils.logger import get_logger

logger = get_logger(__name__)


class HierarchicalContextStrategy(BaseContextStrategy):
    """Стратегия формирования контекста с учетом иерархии.

    Создает обогащенный промпт для эмбеддинга, включающий:
    - Название документа
    - Иерархию заголовков (breadcrumbs)
    - Тип контента и язык (для кода)
    - Сам контент

    Это помогает векторной модели понять контекст чанка
    без необходимости читать весь документ.

    Примеры сформированного текста:

    Для TEXT:
        Document: API Documentation
        Section: Database > Models > User Model
        Content: The User model represents...

    Для CODE:
        Document: API Documentation
        Context: Database > Models > User Model
        Type: Python Code
        Code:
        class User(BaseModel):
            ...
    """

    def __init__(self, include_doc_title: bool = True):
        """Инициализирует стратегию.

        Args:
            include_doc_title: Включать ли название документа в контекст.
        """
        self.include_doc_title = include_doc_title

    def form_vector_text(self, chunk: Chunk, document: Document) -> str:
        """Формирует обогащенный текст для эмбеддинга.

        Args:
            chunk: Чанк для обогащения контекстом.
            document: Родительский документ.

        Returns:
            Структурированный промпт для эмбеддинга.
        """
        log = logger.bind(chunk_id=f"chunk-{chunk.chunk_index}")
        log.trace(f"Формирование контекста для типа {chunk.chunk_type.name}")

        parts: list[str] = []

        # Добавляем название документа
        doc_title = document.metadata.get("title")
        if self.include_doc_title and doc_title:
            parts.append(f"Document: {doc_title}")

        # Извлекаем иерархию заголовков из метаданных
        headers = chunk.metadata.get("headers", [])
        breadcrumbs = " > ".join(headers) if headers else ""

        if breadcrumbs:
            log.trace(f"Breadcrumbs: {breadcrumbs}")

        # Формируем контекст в зависимости от типа чанка
        if chunk.chunk_type == ChunkType.CODE:
            # Для кода используем специальный формат
            if headers:
                parts.append(f"Context: {breadcrumbs}")

            # Указываем тип контента
            if chunk.language:
                parts.append(f"Type: {chunk.language.title()} Code")
            else:
                parts.append("Type: Code")

            # Добавляем сам код
            parts.append("Code:")
            parts.append(chunk.content)

        elif chunk.chunk_type == ChunkType.IMAGE_REF:
            # Для изображений добавляем контекст и метаданные
            if headers:
                parts.append(f"Section: {breadcrumbs}")

            # Проверяем, было ли обогащение через Vision API
            if chunk.metadata.get("_enriched"):
                # Обогащённый чанк: content = описание от Vision
                parts.append("Type: Image")
                parts.append(f"Description: {chunk.content}")

                # Добавляем OCR если есть
                ocr_text = chunk.metadata.get("_vision_ocr")
                if ocr_text:
                    parts.append(f"Visible text: {ocr_text}")

                # Добавляем ключевые слова
                keywords = chunk.metadata.get("_vision_keywords", [])
                if keywords:
                    parts.append(f"Keywords: {', '.join(keywords)}")

                # Оригинальный путь
                original_path = chunk.metadata.get("_original_path", "")
                if original_path:
                    parts.append(f"Source: {original_path}")

                log.trace("Обогащённое изображение с Vision API")
            else:
                # НЕ обогащённый чанк: content = путь к файлу
                parts.append("Type: Image Reference")

                # Добавляем alt-текст и title если есть
                alt_text = chunk.metadata.get("alt", "")
                title_text = chunk.metadata.get("title", "")

                if alt_text:
                    parts.append(f"Description: {alt_text}")
                if title_text:
                    parts.append(f"Title: {title_text}")

                parts.append(f"Source: {chunk.content}")

        elif chunk.chunk_type == ChunkType.AUDIO_REF:
            # Для аудио добавляем транскрипцию или ссылку
            if headers:
                parts.append(f"Section: {breadcrumbs}")

            if chunk.metadata.get("_enriched"):
                # Обогащённый чанк: content = транскрипция
                parts.append("Type: Audio")
                parts.append(f"Transcription: {chunk.content}")

                # Дополнительные метаданные от Audio API
                participants = chunk.metadata.get("_audio_participants", [])
                if participants:
                    parts.append(f"Speakers: {', '.join(participants)}")

                action_items = chunk.metadata.get("_audio_action_items", [])
                if action_items:
                    parts.append(f"Action items: {'; '.join(action_items)}")

                keywords = chunk.metadata.get("_audio_keywords", [])
                if keywords:
                    parts.append(f"Keywords: {', '.join(keywords)}")

                duration = chunk.metadata.get("_audio_duration")
                if duration:
                    parts.append(f"Duration: {duration:.1f}s")

                original_path = chunk.metadata.get("_original_path", "")
                if original_path:
                    parts.append(f"Source: {original_path}")

                log.trace("Обогащённое аудио с Audio API")
            else:
                # НЕ обогащённый чанк: content = путь к файлу
                parts.append("Type: Audio Reference")

                alt_text = chunk.metadata.get("alt", "")
                if alt_text:
                    parts.append(f"Description: {alt_text}")

                parts.append(f"Source: {chunk.content}")

        elif chunk.chunk_type == ChunkType.VIDEO_REF:
            # Для видео добавляем описание или ссылку
            if headers:
                parts.append(f"Section: {breadcrumbs}")

            if chunk.metadata.get("_enriched"):
                # Обогащённый чанк: content = описание от Video API
                parts.append("Type: Video")
                parts.append(f"Description: {chunk.content}")

                # Транскрипция аудио-дорожки
                transcription = chunk.metadata.get("_video_transcription")
                if transcription:
                    parts.append(f"Audio transcription: {transcription}")

                # OCR текст с кадров
                ocr_text = chunk.metadata.get("_video_ocr")
                if ocr_text:
                    parts.append(f"Visible text: {ocr_text}")

                keywords = chunk.metadata.get("_video_keywords", [])
                if keywords:
                    parts.append(f"Keywords: {', '.join(keywords)}")

                duration = chunk.metadata.get("_video_duration")
                if duration:
                    parts.append(f"Duration: {duration:.1f}s")

                original_path = chunk.metadata.get("_original_path", "")
                if original_path:
                    parts.append(f"Source: {original_path}")

                log.trace("Обогащённое видео с Video API")
            else:
                # НЕ обогащённый чанк: content = путь к файлу
                parts.append("Type: Video Reference")

                alt_text = chunk.metadata.get("alt", "")
                if alt_text:
                    parts.append(f"Description: {alt_text}")

                parts.append(f"Source: {chunk.content}")

        else:
            # Для обычного текста
            if headers:
                parts.append(f"Section: {breadcrumbs}")

            # Проверяем, является ли это цитатой
            if chunk.metadata.get("quote"):
                parts.append("Type: Quote")

            parts.append("Content:")
            parts.append(chunk.content)

        result = "\n".join(parts)
        context_size = len(result) - len(chunk.content)
        log.info(
            f"Контекст сформирован: type={chunk.chunk_type.name}, "
            f"добавлено +{context_size} символов контекста"
        )

        return result
