"""E2E тесты: Сценарий C — Медиа-обогащение.

РЕАЛЬНЫЕ вызовы Gemini Vision/Audio/Video API.
Все промпты, ответы, результаты записываются в отчёт.

Запуск:
    poetry run pytest tests/e2e/audit/test_media_audit.py -v -s

Требуется: GEMINI_API_KEY в .env
"""

import os
import time
import mimetypes
import pytest
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from semantic_core.domain.media import MediaRequest, MediaResource
from semantic_core.domain.media import MediaAnalysisResult
from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer
from semantic_core.infrastructure.gemini.video_analyzer import GeminiVideoAnalyzer

from tests.e2e.audit.conftest import MediaInspection, AuditCollector


def create_media_resource(path: Path, media_type: str) -> MediaResource:
    """Создаёт MediaResource с автоопределением mime_type."""
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        ext_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
        }
        mime_type = ext_map.get(path.suffix.lower(), "application/octet-stream")
    
    return MediaResource(
        path=path,
        media_type=media_type,
        mime_type=mime_type,
    )


# ============================================================================
# Фикстуры для анализаторов
# ============================================================================


@pytest.fixture(scope="session")
def api_key():
    """API ключ из окружения."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def image_analyzer(api_key: str) -> GeminiImageAnalyzer:
    """Реальный анализатор изображений."""
    return GeminiImageAnalyzer(api_key=api_key)


@pytest.fixture(scope="session")
def audio_analyzer(api_key: str) -> GeminiAudioAnalyzer:
    """Реальный анализатор аудио."""
    return GeminiAudioAnalyzer(api_key=api_key)


@pytest.fixture(scope="session")
def video_analyzer(api_key: str) -> GeminiVideoAnalyzer:
    """Реальный анализатор видео."""
    return GeminiVideoAnalyzer(api_key=api_key)


# ============================================================================
# Тесты изображений
# ============================================================================


class TestImageAnalysis:
    """Реальный анализ изображений через Gemini Vision."""
    
    def test_cat_photo_analysis(
        self,
        image_analyzer: GeminiImageAnalyzer,
        test_assets_path: Path,
        audit_collector: AuditCollector,
    ):
        """Анализ фото кота."""
        image_path = test_assets_path / "cat_photo.png"
        if not image_path.exists():
            pytest.skip(f"File not found: {image_path}")
        
        resource = create_media_resource(image_path, "image")
        request = MediaRequest(
            resource=resource,
            context_text="A personal photo from a pet blog",
            user_prompt="Describe this pet photo for a family album.",
        )
        
        start_time = time.perf_counter()
        result = image_analyzer.analyze(request)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        # Записываем в отчёт
        inspection = MediaInspection(
            asset_path="cat_photo.png",
            asset_absolute_path=str(image_path),
            media_type="image",
            file_size_bytes=image_path.stat().st_size,
            surrounding_text_before="A personal photo from a pet blog",
            surrounding_text_after="",
            system_prompt="You are an image analyst creating descriptions for semantic search...",
            user_prompt="Describe this pet photo for a family album.",
            model_name=image_analyzer.model,
            response_raw={
                "alt_text": result.alt_text,
                "description": result.description,
                "keywords": result.keywords,
                "ocr_text": result.ocr_text,
            },
            response_parsed=result,
            final_chunk_content=f"[IMAGE: cat_photo.png]\n\n{result.description}\n\nKeywords: {', '.join(result.keywords or [])}",
            processing_time_ms=processing_time,
        )
        audit_collector.add_media(inspection)
        
        # Проверки
        assert result is not None
        assert result.description
        assert len(result.description) > 20
        assert result.keywords
    
    def test_eiffel_tower_analysis(
        self,
        image_analyzer: GeminiImageAnalyzer,
        test_assets_path: Path,
        audit_collector: AuditCollector,
    ):
        """Анализ фото Эйфелевой башни."""
        image_path = test_assets_path / "eiffel_tower.jpg"
        if not image_path.exists():
            pytest.skip(f"File not found: {image_path}")
        
        resource = create_media_resource(image_path, "image")
        request = MediaRequest(
            resource=resource,
            context_text="Travel blog post about Paris",
            user_prompt="Describe this landmark photo for a travel guide.",
        )
        
        start_time = time.perf_counter()
        result = image_analyzer.analyze(request)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        inspection = MediaInspection(
            asset_path="eiffel_tower.jpg",
            asset_absolute_path=str(image_path),
            media_type="image",
            file_size_bytes=image_path.stat().st_size,
            surrounding_text_before="Travel blog post about Paris",
            surrounding_text_after="",
            system_prompt="You are an image analyst...",
            user_prompt="Describe this landmark photo for a travel guide.",
            model_name=image_analyzer.model,
            response_raw={
                "alt_text": result.alt_text,
                "description": result.description,
                "keywords": result.keywords,
                "ocr_text": result.ocr_text,
            },
            response_parsed=result,
            final_chunk_content=f"[IMAGE: eiffel_tower.jpg]\n\n{result.description}",
            processing_time_ms=processing_time,
        )
        audit_collector.add_media(inspection)
        
        assert result is not None
        assert "eiffel" in result.description.lower() or "tower" in result.description.lower() or "paris" in result.description.lower()
    
    def test_code_screen_ocr(
        self,
        image_analyzer: GeminiImageAnalyzer,
        test_assets_path: Path,
        audit_collector: AuditCollector,
    ):
        """Анализ скриншота кода (OCR)."""
        image_path = test_assets_path / "code_screen.jpg"
        if not image_path.exists():
            pytest.skip(f"File not found: {image_path}")
        
        resource = create_media_resource(image_path, "image")
        request = MediaRequest(
            resource=resource,
            context_text="Technical documentation screenshot",
            user_prompt="Extract the code from this screenshot. Focus on OCR.",
        )
        
        start_time = time.perf_counter()
        result = image_analyzer.analyze(request)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        inspection = MediaInspection(
            asset_path="code_screen.jpg",
            asset_absolute_path=str(image_path),
            media_type="image",
            file_size_bytes=image_path.stat().st_size,
            surrounding_text_before="Technical documentation screenshot",
            surrounding_text_after="",
            system_prompt="You are an image analyst...",
            user_prompt="Extract the code from this screenshot. Focus on OCR.",
            model_name=image_analyzer.model,
            response_raw={
                "alt_text": result.alt_text,
                "description": result.description,
                "keywords": result.keywords,
                "ocr_text": result.ocr_text,
            },
            response_parsed=result,
            final_chunk_content=f"[IMAGE: code_screen.jpg]\n\nOCR:\n{result.ocr_text or 'No text detected'}\n\n{result.description}",
            processing_time_ms=processing_time,
        )
        audit_collector.add_media(inspection)
        
        assert result is not None
        assert result.description


# ============================================================================
# Тесты аудио
# ============================================================================


class TestAudioAnalysis:
    """Реальный анализ аудио через Gemini Audio."""
    
    def test_slides_ideas_transcription(
        self,
        audio_analyzer: GeminiAudioAnalyzer,
        test_assets_path: Path,
        audit_collector: AuditCollector,
    ):
        """Транскрипция голосового сообщения на русском."""
        audio_path = test_assets_path / "slides_ideas_audio.ogg"
        if not audio_path.exists():
            pytest.skip(f"File not found: {audio_path}")
        
        resource = create_media_resource(audio_path, "audio")
        request = MediaRequest(
            resource=resource,
            context_text="Voice memo in Russian about presentation slides",
            user_prompt="Transcribe this voice memo and summarize the ideas.",
        )
        
        start_time = time.perf_counter()
        result = audio_analyzer.analyze(request)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        inspection = MediaInspection(
            asset_path="slides_ideas_audio.ogg",
            asset_absolute_path=str(audio_path),
            media_type="audio",
            file_size_bytes=audio_path.stat().st_size,
            surrounding_text_before="Voice memo in Russian",
            surrounding_text_after="",
            system_prompt="You are an audio analyst...",
            user_prompt="Transcribe this voice memo and summarize the ideas.",
            model_name=audio_analyzer.model,
            response_raw={
                "description": result.description,
                "transcription": result.transcription,
                "keywords": result.keywords,
                "participants": result.participants,
                "duration_seconds": result.duration_seconds,
            },
            response_parsed=result,
            final_chunk_content=f"[AUDIO: slides_ideas_audio.ogg]\n\nTranscription:\n{result.transcription or 'N/A'}\n\nSummary: {result.description}",
            processing_time_ms=processing_time,
        )
        audit_collector.add_media(inspection)
        
        assert result is not None
        assert result.description


# ============================================================================
# Тесты видео
# ============================================================================


class TestVideoAnalysis:
    """Реальный анализ видео через Gemini Video."""
    
    def test_module_init_demo(
        self,
        video_analyzer: GeminiVideoAnalyzer,
        test_assets_path: Path,
        audit_collector: AuditCollector,
    ):
        """Анализ демо-видео инициализации модуля."""
        video_path = test_assets_path / "module_init_demo.mp4"
        if not video_path.exists():
            pytest.skip(f"File not found: {video_path}")
        
        resource = create_media_resource(video_path, "video")
        request = MediaRequest(
            resource=resource,
            context_text="Technical demo video showing module initialization",
            user_prompt="Describe what happens in this demo. Extract any visible code.",
        )
        
        start_time = time.perf_counter()
        result = video_analyzer.analyze(request)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        inspection = MediaInspection(
            asset_path="module_init_demo.mp4",
            asset_absolute_path=str(video_path),
            media_type="video",
            file_size_bytes=video_path.stat().st_size,
            surrounding_text_before="Technical demo video",
            surrounding_text_after="",
            system_prompt="You are a video analyst...",
            user_prompt="Describe what happens in this demo. Extract any visible code.",
            model_name=video_analyzer.model,
            response_raw={
                "description": result.description,
                "transcription": result.transcription,
                "ocr_text": result.ocr_text,
                "keywords": result.keywords,
                "duration_seconds": result.duration_seconds,
            },
            response_parsed=result,
            final_chunk_content=f"[VIDEO: module_init_demo.mp4]\n\n{result.description}\n\nTranscript: {result.transcription or 'N/A'}\n\nOCR: {result.ocr_text or 'N/A'}",
            processing_time_ms=processing_time,
        )
        audit_collector.add_media(inspection)
        
        assert result is not None
        assert result.description
    
    def test_new_year_greeting(
        self,
        video_analyzer: GeminiVideoAnalyzer,
        test_assets_path: Path,
        audit_collector: AuditCollector,
    ):
        """Анализ новогоднего поздравления."""
        video_path = test_assets_path / "new_year_greeting.mp4"
        if not video_path.exists():
            pytest.skip(f"File not found: {video_path}")
        
        resource = create_media_resource(video_path, "video")
        request = MediaRequest(
            resource=resource,
            context_text="New Year greeting video in Russian",
            user_prompt="Describe this greeting video and transcribe what is said.",
        )
        
        start_time = time.perf_counter()
        result = video_analyzer.analyze(request)
        processing_time = (time.perf_counter() - start_time) * 1000
        
        inspection = MediaInspection(
            asset_path="new_year_greeting.mp4",
            asset_absolute_path=str(video_path),
            media_type="video",
            file_size_bytes=video_path.stat().st_size,
            surrounding_text_before="New Year greeting video in Russian",
            surrounding_text_after="",
            system_prompt="You are a video analyst...",
            user_prompt="Describe this greeting video and transcribe what is said.",
            model_name=video_analyzer.model,
            response_raw={
                "description": result.description,
                "transcription": result.transcription,
                "keywords": result.keywords,
                "duration_seconds": result.duration_seconds,
            },
            response_parsed=result,
            final_chunk_content=f"[VIDEO: new_year_greeting.mp4]\n\n{result.description}\n\nTranscript: {result.transcription or 'N/A'}",
            processing_time_ms=processing_time,
        )
        audit_collector.add_media(inspection)
        
        assert result is not None


# ============================================================================
# Инвентаризация
# ============================================================================


class TestMediaInventory:
    """Проверка наличия медиа-файлов."""
    
    def test_list_all_media_files(self, test_assets_path: Path):
        """Выводит список всех медиа для визуальной проверки."""
        image_ext = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        audio_ext = {".mp3", ".ogg", ".wav", ".m4a"}
        video_ext = {".mp4", ".webm", ".mov", ".avi"}
        
        media_files = {"images": [], "audio": [], "video": []}
        
        for file in test_assets_path.iterdir():
            if file.is_file():
                ext = file.suffix.lower()
                if ext in image_ext:
                    media_files["images"].append(file.name)
                elif ext in audio_ext:
                    media_files["audio"].append(file.name)
                elif ext in video_ext:
                    media_files["video"].append(file.name)
        
        print("\n=== MEDIA INVENTORY ===")
        print(f"Images: {media_files['images']}")
        print(f"Audio: {media_files['audio']}")
        print(f"Video: {media_files['video']}")
        
        total = sum(len(v) for v in media_files.values())
        assert total > 0, "No media files found in tests/asests/"
