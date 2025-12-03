"""Integration-тесты: Markdown + Media.

Проверяем интеграцию парсинга Markdown с медиа-обработкой:
- Поиск ссылок ![Image](path) в Markdown
- Извлечение ChunkType.IMAGE_REF сегментов
- Создание задач в MediaTaskModel
- (TODO) Роутинг audio/video ссылок на соответствующие анализаторы

Эти тесты НЕ требуют реальных медиа-файлов (используют моки).
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from semantic_core.domain import ChunkType
from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser
from semantic_core.processing.splitters.smart_splitter import SmartSplitter


# ============================================================================
# Парсинг Markdown с медиа-ссылками
# ============================================================================


class TestMarkdownImageParsing:
    """Тесты парсинга изображений в Markdown."""

    @pytest.fixture
    def parser(self):
        """Экземпляр MarkdownNodeParser."""
        return MarkdownNodeParser()

    def test_parse_image_ref(self, parser):
        """Парсер находит изображение и создаёт IMAGE_REF сегмент."""
        md = """
# Урок 1

![Diagram](images/diagram.png)
"""
        segments = list(parser.parse(md))

        # Должен быть сегмент IMAGE_REF
        image_segments = [s for s in segments if s.segment_type == ChunkType.IMAGE_REF]
        assert len(image_segments) == 1

        img = image_segments[0]
        assert img.content == "images/diagram.png"
        assert img.headers == ["Урок 1"]

    def test_parse_image_with_alt_text(self, parser):
        """Alt-text сохраняется в metadata."""
        md = "![Architecture Diagram](arch.png)"

        segments = list(parser.parse(md))
        image_segments = [s for s in segments if s.segment_type == ChunkType.IMAGE_REF]

        assert len(image_segments) == 1
        assert image_segments[0].metadata["alt"] == "Architecture Diagram"

    def test_parse_multiple_images(self, parser):
        """Несколько изображений парсятся отдельно."""
        md = """
# Section 1

![Image 1](img1.png)

# Section 2

![Image 2](img2.png)
"""
        segments = list(parser.parse(md))
        image_segments = [s for s in segments if s.segment_type == ChunkType.IMAGE_REF]

        assert len(image_segments) == 2
        assert image_segments[0].content == "img1.png"
        assert image_segments[0].headers == ["Section 1"]
        assert image_segments[1].content == "img2.png"
        assert image_segments[1].headers == ["Section 2"]

    def test_image_with_text_is_text_segment(self, parser):
        """Если есть текст рядом с картинкой — это TEXT сегмент."""
        md = "Some text ![img](test.png) more text"

        segments = list(parser.parse(md))

        # Не должно быть IMAGE_REF, т.к. есть текст
        image_segments = [s for s in segments if s.segment_type == ChunkType.IMAGE_REF]
        text_segments = [s for s in segments if s.segment_type == ChunkType.TEXT]

        assert len(image_segments) == 0
        assert len(text_segments) == 1

    def test_parse_image_preserves_headers_hierarchy(self, parser):
        """Иерархия заголовков сохраняется для IMAGE_REF."""
        md = """
# Chapter 1

## Section 1.1

### Subsection 1.1.1

![Deep Image](deep.png)
"""
        segments = list(parser.parse(md))
        image_segments = [s for s in segments if s.segment_type == ChunkType.IMAGE_REF]

        assert len(image_segments) == 1
        assert image_segments[0].headers == [
            "Chapter 1",
            "Section 1.1",
            "Subsection 1.1.1",
        ]


# ============================================================================
# Smart Splitter + Медиа-сегменты
# ============================================================================


class TestSmartSplitterMedia:
    """Тесты SmartSplitter с медиа-контентом."""

    @pytest.fixture
    def splitter(self):
        """SmartSplitter с Markdown парсером."""
        parser = MarkdownNodeParser()
        return SmartSplitter(
            parser=parser,
            chunk_size=500,
            code_chunk_size=1000,
            preserve_code=True,
        )

    def test_image_becomes_separate_chunk(self, splitter):
        """IMAGE_REF становится отдельным чанком."""
        from semantic_core.domain import Document

        doc = Document(
            content="""
# Tutorial

Some intro text about the topic.

![Main Diagram](diagram.png)

More explanation text.
""",
            metadata={"title": "Test Tutorial"},
        )

        chunks = splitter.split(doc)

        # Ищем IMAGE_REF чанк
        image_chunks = [c for c in chunks if c.chunk_type == ChunkType.IMAGE_REF]

        assert len(image_chunks) == 1
        assert image_chunks[0].content == "diagram.png"

    def test_mixed_content_order_preserved(self, splitter):
        """Порядок TEXT и IMAGE_REF сохраняется."""
        from semantic_core.domain import Document

        doc = Document(
            content="""
# Doc

Text 1

![Image A](a.png)

Text 2

![Image B](b.png)

Text 3
""",
            metadata={"title": "Mixed Doc"},
        )

        chunks = splitter.split(doc)

        # Проверяем порядок типов
        types = [c.chunk_type for c in chunks]

        # Должен быть: TEXT, IMAGE_REF, TEXT, IMAGE_REF, TEXT
        expected_pattern = [
            ChunkType.TEXT,
            ChunkType.IMAGE_REF,
            ChunkType.TEXT,
            ChunkType.IMAGE_REF,
            ChunkType.TEXT,
        ]
        assert types == expected_pattern


# ============================================================================
# Определение типа медиа по расширению
# ============================================================================


class TestMediaTypeDetection:
    """Тесты определения типа медиа по расширению/MIME-типу."""

    def test_audio_extensions_detected(self):
        """Аудио-расширения определяются корректно."""
        from semantic_core.infrastructure.media.utils.audio import is_audio_supported

        assert is_audio_supported("audio/mpeg")  # mp3
        assert is_audio_supported("audio/wav")
        assert is_audio_supported("audio/ogg")
        assert not is_audio_supported("video/mp4")
        assert not is_audio_supported("image/png")

    def test_video_extensions_detected(self):
        """Видео-расширения определяются корректно."""
        from semantic_core.infrastructure.media.utils.video import is_video_supported

        assert is_video_supported("video/mp4")
        assert is_video_supported("video/webm")
        assert is_video_supported("video/quicktime")  # .mov
        assert not is_video_supported("audio/mp3")
        assert not is_video_supported("image/png")


# ============================================================================
# MediaQueueProcessor роутинг
# ============================================================================


class TestMediaQueueRouting:
    """Тесты роутинга задач на нужные анализаторы."""

    @pytest.fixture
    def mock_image_analyzer(self):
        """Mock анализатор изображений."""
        from semantic_core.domain.media import MediaAnalysisResult

        analyzer = MagicMock()
        analyzer.analyze.return_value = MediaAnalysisResult(
            description="Test image",
            alt_text="Alt",
            keywords=["test"],
        )
        return analyzer

    @pytest.fixture
    def mock_audio_analyzer(self):
        """Mock анализатор аудио."""
        from semantic_core.domain.media import MediaAnalysisResult

        analyzer = MagicMock()
        analyzer.analyze.return_value = MediaAnalysisResult(
            description="Audio content",
            alt_text="Audio",
            keywords=["speech"],
            transcription="Hello world",
        )
        return analyzer

    @pytest.fixture
    def mock_video_analyzer(self):
        """Mock анализатор видео."""
        from semantic_core.domain.media import MediaAnalysisResult

        analyzer = MagicMock()
        analyzer.analyze.return_value = MediaAnalysisResult(
            description="Video content",
            alt_text="Video",
            keywords=["presentation"],
            transcription="Welcome to the tutorial",
            duration_seconds=60.0,
        )
        return analyzer

    @pytest.fixture
    def rate_limiter(self):
        """Mock rate limiter."""
        limiter = MagicMock()
        limiter.wait.return_value = None
        return limiter

    def test_image_routes_to_image_analyzer(
        self,
        mock_image_analyzer,
        mock_audio_analyzer,
        mock_video_analyzer,
        rate_limiter,
    ):
        """image/* роутится на image_analyzer."""
        from semantic_core.core.media_queue import MediaQueueProcessor
        from semantic_core.domain.media import MediaRequest, MediaResource

        processor = MediaQueueProcessor(
            image_analyzer=mock_image_analyzer,
            audio_analyzer=mock_audio_analyzer,
            video_analyzer=mock_video_analyzer,
            rate_limiter=rate_limiter,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=Path("test.png"),
                media_type="image",
                mime_type="image/png",
            )
        )

        result = processor._route_and_analyze(request, "image/png")

        mock_image_analyzer.analyze.assert_called_once()
        mock_audio_analyzer.analyze.assert_not_called()
        mock_video_analyzer.analyze.assert_not_called()
        assert result.description == "Test image"

    def test_audio_routes_to_audio_analyzer(
        self,
        mock_image_analyzer,
        mock_audio_analyzer,
        mock_video_analyzer,
        rate_limiter,
    ):
        """audio/* роутится на audio_analyzer."""
        from semantic_core.core.media_queue import MediaQueueProcessor
        from semantic_core.domain.media import MediaRequest, MediaResource

        processor = MediaQueueProcessor(
            image_analyzer=mock_image_analyzer,
            audio_analyzer=mock_audio_analyzer,
            video_analyzer=mock_video_analyzer,
            rate_limiter=rate_limiter,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=Path("speech.mp3"),
                media_type="audio",
                mime_type="audio/mpeg",
            )
        )

        result = processor._route_and_analyze(request, "audio/mpeg")

        mock_audio_analyzer.analyze.assert_called_once()
        mock_image_analyzer.analyze.assert_not_called()
        mock_video_analyzer.analyze.assert_not_called()
        assert result.transcription == "Hello world"

    def test_video_routes_to_video_analyzer(
        self,
        mock_image_analyzer,
        mock_audio_analyzer,
        mock_video_analyzer,
        rate_limiter,
    ):
        """video/* роутится на video_analyzer."""
        from semantic_core.core.media_queue import MediaQueueProcessor
        from semantic_core.domain.media import MediaRequest, MediaResource

        processor = MediaQueueProcessor(
            image_analyzer=mock_image_analyzer,
            audio_analyzer=mock_audio_analyzer,
            video_analyzer=mock_video_analyzer,
            rate_limiter=rate_limiter,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=Path("lecture.mp4"),
                media_type="video",
                mime_type="video/mp4",
            )
        )

        result = processor._route_and_analyze(request, "video/mp4")

        mock_video_analyzer.analyze.assert_called_once()
        mock_image_analyzer.analyze.assert_not_called()
        mock_audio_analyzer.analyze.assert_not_called()
        assert result.duration_seconds == 60.0

    def test_audio_without_analyzer_raises(self, mock_image_analyzer, rate_limiter):
        """Если audio_analyzer не настроен — ValueError."""
        from semantic_core.core.media_queue import MediaQueueProcessor
        from semantic_core.domain.media import MediaRequest, MediaResource

        processor = MediaQueueProcessor(
            image_analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
            # audio_analyzer=None  # Не передаём
        )

        request = MediaRequest(
            resource=MediaResource(
                path=Path("speech.mp3"),
                media_type="audio",
                mime_type="audio/mpeg",
            )
        )

        with pytest.raises(ValueError, match="Audio analyzer not configured"):
            processor._route_and_analyze(request, "audio/mpeg")

    def test_video_without_analyzer_raises(self, mock_image_analyzer, rate_limiter):
        """Если video_analyzer не настроен — ValueError."""
        from semantic_core.core.media_queue import MediaQueueProcessor
        from semantic_core.domain.media import MediaRequest, MediaResource

        processor = MediaQueueProcessor(
            image_analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
            # video_analyzer=None  # Не передаём
        )

        request = MediaRequest(
            resource=MediaResource(
                path=Path("lecture.mp4"),
                media_type="video",
                mime_type="video/mp4",
            )
        )

        with pytest.raises(ValueError, match="Video analyzer not configured"):
            processor._route_and_analyze(request, "video/mp4")

    def test_unsupported_type_raises(self, mock_image_analyzer, rate_limiter):
        """Неизвестный MIME-тип — ValueError."""
        from semantic_core.core.media_queue import MediaQueueProcessor
        from semantic_core.domain.media import MediaRequest, MediaResource

        processor = MediaQueueProcessor(
            image_analyzer=mock_image_analyzer,
            rate_limiter=rate_limiter,
        )

        request = MediaRequest(
            resource=MediaResource(
                path=Path("doc.pdf"),
                media_type="application",
                mime_type="application/pdf",
            )
        )

        with pytest.raises(ValueError, match="Unsupported media type"):
            processor._route_and_analyze(request, "application/pdf")


# ============================================================================
# Markdown с audio/video ссылками (Phase 6.5)
# ============================================================================


class TestMarkdownAudioVideoLinks:
    """Тесты для Phase 6.5: Audio/Video в Markdown.

    Парсер определяет тип медиа по расширению файла:
    - .mp3, .wav, .ogg, .flac, .aac, .aiff → AUDIO_REF
    - .mp4, .mov, .avi, .mkv, .webm → VIDEO_REF
    - .png, .jpg, .jpeg, .gif, .webp, .svg, .bmp → IMAGE_REF
    """

    @pytest.fixture
    def parser(self):
        return MarkdownNodeParser()

    def test_audio_link_parsed_as_audio_ref(self, parser):
        """Аудио-ссылка ![Audio](file.mp3) → AUDIO_REF."""
        md = "![Audio](audio/speech.mp3)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.AUDIO_REF
        assert segments[0].content == "audio/speech.mp3"
        assert segments[0].metadata.get("alt") == "Audio"

    def test_video_link_parsed_as_video_ref(self, parser):
        """Видео-ссылка ![Video](file.mp4) → VIDEO_REF."""
        md = "![Video](video/slides.mp4)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.VIDEO_REF
        assert segments[0].content == "video/slides.mp4"
        assert segments[0].metadata.get("alt") == "Video"

    def test_wav_audio_detected(self, parser):
        """WAV аудио-файл определяется как AUDIO_REF."""
        md = "![Noise](../audio/noise.wav)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.AUDIO_REF
        assert segments[0].content == "../audio/noise.wav"

    def test_mov_video_detected(self, parser):
        """MOV видео-файл определяется как VIDEO_REF."""
        md = "![Screen Recording](video/screen.mov)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.VIDEO_REF

    def test_link_syntax_audio_detected(self, parser):
        """Ссылка [text](file.mp3) → AUDIO_REF."""
        md = "[Послушать запись](audio/speech.mp3)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.AUDIO_REF
        assert segments[0].content == "audio/speech.mp3"
        assert segments[0].metadata.get("alt") == "Послушать запись"

    def test_link_syntax_video_detected(self, parser):
        """Ссылка [text](file.mp4) → VIDEO_REF."""
        md = "[Смотреть видео](video/slides.mp4)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.VIDEO_REF
        assert segments[0].content == "video/slides.mp4"

    def test_link_syntax_image_not_detected(self, parser):
        """Ссылка [text](image.png) НЕ создаёт IMAGE_REF (только text)."""
        md = "[Click here](images/diagram.png)"

        segments = list(parser.parse(md))

        # Обычная ссылка на картинку не создаёт медиа-сегмент
        # (только ![](path) синтаксис создаёт IMAGE_REF)
        media_segments = [
            s
            for s in segments
            if s.segment_type
            in (ChunkType.IMAGE_REF, ChunkType.AUDIO_REF, ChunkType.VIDEO_REF)
        ]
        assert len(media_segments) == 0

    def test_post_with_mixed_media_from_fixture(self, parser):
        """Парсинг тестового Markdown с аудио и видео ссылками."""
        md = """
# Урок 1: Введение в Semantic Core

Добро пожаловать на наш курс!

## Аудио-материалы

Послушайте введение:

![Audio](../audio/speech.mp3)

## Видео-материалы

Посмотрите слайды презентации:

![Video](../video/slides.mp4)

## Заключение

Это тестовый Markdown-файл.
"""
        segments = list(parser.parse(md))

        # Находим аудио-сегменты
        audio_segments = [s for s in segments if s.segment_type == ChunkType.AUDIO_REF]
        assert len(audio_segments) == 1
        assert audio_segments[0].content == "../audio/speech.mp3"
        assert audio_segments[0].headers == [
            "Урок 1: Введение в Semantic Core",
            "Аудио-материалы",
        ]

        # Находим видео-сегменты
        video_segments = [s for s in segments if s.segment_type == ChunkType.VIDEO_REF]
        assert len(video_segments) == 1
        assert video_segments[0].content == "../video/slides.mp4"
        assert video_segments[0].headers == [
            "Урок 1: Введение в Semantic Core",
            "Видео-материалы",
        ]

    def test_image_still_detected_as_image_ref(self, parser):
        """Картинка ![](image.png) → IMAGE_REF (не перепутать с video/audio)."""
        md = "![Diagram](images/architecture.png)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.IMAGE_REF
        assert segments[0].content == "images/architecture.png"

    def test_unknown_extension_fallback_to_image(self, parser):
        """Неизвестное расширение в ![]() → IMAGE_REF fallback."""
        md = "![Unknown](files/document.pdf)"

        segments = list(parser.parse(md))

        assert len(segments) == 1
        assert segments[0].segment_type == ChunkType.IMAGE_REF  # fallback

    def test_all_audio_extensions(self, parser):
        """Все поддерживаемые аудио-расширения детектируются."""
        extensions = [".mp3", ".wav", ".ogg", ".flac", ".aac", ".aiff"]

        for ext in extensions:
            md = f"![Audio](audio/file{ext})"
            segments = list(parser.parse(md))
            assert segments[0].segment_type == ChunkType.AUDIO_REF, f"Failed for {ext}"

    def test_all_video_extensions(self, parser):
        """Все поддерживаемые видео-расширения детектируются."""
        extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]

        for ext in extensions:
            md = f"![Video](video/file{ext})"
            segments = list(parser.parse(md))
            assert segments[0].segment_type == ChunkType.VIDEO_REF, f"Failed for {ext}"
