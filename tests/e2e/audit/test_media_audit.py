"""E2E тесты: Сценарий C — Медиа-обогащение.

Проверяет промпты и ответы Vision/Audio/Video API.
Использует реальные медиа-файлы из tests/asests/

Запуск:
    # С моками (без API)
    pytest tests/e2e/audit/test_media_audit.py -v -s
    
    # С реальным API (нужен SEMANTIC_GEMINI_API_KEY)
    SEMANTIC_GEMINI_API_KEY=your_key pytest tests/e2e/audit/test_media_audit.py -v -s

Отчёты сохраняются в: tests/audit_reports/YYYY-MM-DD_HH-MM/
"""

import os
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from semantic_core.domain.media import MediaAnalysisResult


# Проверяем наличие API ключа для реальных тестов
HAS_API_KEY = bool(os.environ.get("SEMANTIC_GEMINI_API_KEY"))


# ============================================================================
# Тесты с моками (работают всегда)
# ============================================================================


class TestMediaAuditMocked:
    """Тесты медиа-обогащения с mock анализаторами.
    
    Эти тесты НЕ требуют API ключа и проверяют структуру данных.
    """
    
    def test_image_analysis_mock(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Тест обработки изображения с mock-анализатором."""
        from tests.e2e.audit.conftest import MediaInspection
        
        image_file = test_assets_path / "cat_photo.png"
        if not image_file.exists():
            pytest.skip(f"Изображение не найдено: {image_file}")
        
        # Mock ответ
        mock_response = MediaAnalysisResult(
            description="Фотография рыжего кота, сидящего на подоконнике",
            alt_text="Orange cat on windowsill",
            keywords=["cat", "pet", "animal", "window"],
            ocr_text=None,
        )
        
        inspection = MediaInspection(
            asset_path="cat_photo.png",
            asset_absolute_path=str(image_file),
            media_type="image",
            file_size_bytes=image_file.stat().st_size,
            surrounding_text_before="Вот фото моего кота:",
            surrounding_text_after="Он любит сидеть на окне.",
            system_prompt="Analyze this image and describe what you see.",
            user_prompt="Describe this cat photo in detail.",
            model_name="gemini-2.0-flash (mock)",
            response_raw={"description": mock_response.description},
            response_parsed=mock_response,
            final_chunk_content=f"[IMAGE: cat_photo.png]\n{mock_response.description}",
            processing_time_ms=150.0,
        )
        
        pipeline_inspector.add_media_inspection(inspection)
        
        # Создаём фейковый отчёт чтобы инспекция сохранилась
        from tests.e2e.audit.conftest import InspectionReport
        if not pipeline_inspector.reports:
            pipeline_inspector.reports.append(
                InspectionReport(
                    file_path="media_test",
                    file_content_preview="",
                )
            )
        
        assert inspection.media_type == "image"
        assert inspection.file_size_bytes > 0
    
    def test_audio_analysis_mock(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Тест обработки аудио с mock-анализатором."""
        from tests.e2e.audit.conftest import MediaInspection, InspectionReport
        
        audio_file = test_assets_path / "slides_ideas_audio.ogg"
        if not audio_file.exists():
            pytest.skip(f"Аудио не найдено: {audio_file}")
        
        mock_response = MediaAnalysisResult(
            description="Запись голосового сообщения с идеями для презентации",
            alt_text="Voice memo about presentation slides",
            keywords=["slides", "presentation", "ideas", "voice"],
            transcription="Нужно добавить слайд про архитектуру и ещё один про API...",
            participants=["Автор"],
            duration_seconds=45.0,
        )
        
        inspection = MediaInspection(
            asset_path="slides_ideas_audio.ogg",
            asset_absolute_path=str(audio_file),
            media_type="audio",
            file_size_bytes=audio_file.stat().st_size,
            surrounding_text_before="",
            surrounding_text_after="",
            system_prompt="Transcribe and analyze this audio recording.",
            user_prompt="What is discussed in this audio?",
            model_name="gemini-2.0-flash (mock)",
            response_raw={
                "description": mock_response.description,
                "transcription": mock_response.transcription,
            },
            response_parsed=mock_response,
            final_chunk_content=f"[AUDIO: slides_ideas_audio.ogg]\n{mock_response.transcription}",
            processing_time_ms=250.0,
        )
        
        if not pipeline_inspector.reports:
            pipeline_inspector.reports.append(
                InspectionReport(
                    file_path="media_test",
                    file_content_preview="",
                )
            )
        
        pipeline_inspector.add_media_inspection(inspection)
        
        assert inspection.media_type == "audio"
        assert mock_response.duration_seconds == 45.0
    
    def test_video_analysis_mock(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Тест обработки видео с mock-анализатором."""
        from tests.e2e.audit.conftest import MediaInspection, InspectionReport
        
        video_file = test_assets_path / "module_init_demo.mp4"
        if not video_file.exists():
            pytest.skip(f"Видео не найдено: {video_file}")
        
        mock_response = MediaAnalysisResult(
            description="Демонстрация инициализации модуля в IDE",
            alt_text="Module initialization demo",
            keywords=["module", "init", "demo", "IDE", "Python"],
            transcription="Сейчас я покажу как инициализировать модуль...",
            ocr_text="class MyModule:\n    def __init__(self):",
            duration_seconds=30.0,
        )
        
        inspection = MediaInspection(
            asset_path="module_init_demo.mp4",
            asset_absolute_path=str(video_file),
            media_type="video",
            file_size_bytes=video_file.stat().st_size,
            surrounding_text_before="Смотри демо:",
            surrounding_text_after="Надеюсь понятно!",
            system_prompt="Analyze this video, extract key frames and transcribe audio.",
            user_prompt="Describe what's happening in this demo video.",
            model_name="gemini-2.0-flash (mock)",
            response_raw={
                "description": mock_response.description,
                "transcription": mock_response.transcription,
                "ocr_text": mock_response.ocr_text,
            },
            response_parsed=mock_response,
            final_chunk_content=f"[VIDEO: module_init_demo.mp4]\n{mock_response.description}\n\nTranscript: {mock_response.transcription}",
            processing_time_ms=500.0,
        )
        
        if not pipeline_inspector.reports:
            pipeline_inspector.reports.append(
                InspectionReport(
                    file_path="media_test",
                    file_content_preview="",
                )
            )
        
        pipeline_inspector.add_media_inspection(inspection)
        
        assert inspection.media_type == "video"
        assert mock_response.duration_seconds == 30.0


# ============================================================================
# Тесты с реальным API (требуют SEMANTIC_GEMINI_API_KEY)
# ============================================================================


@pytest.mark.skipif(not HAS_API_KEY, reason="SEMANTIC_GEMINI_API_KEY not set")
class TestMediaAuditReal:
    """Тесты медиа-обогащения с реальным Gemini API.
    
    Требуют переменную окружения SEMANTIC_GEMINI_API_KEY.
    """
    
    def test_real_image_analysis(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Реальный анализ изображения через Gemini Vision API."""
        from tests.e2e.audit.conftest import MediaInspection, InspectionReport
        from semantic_core.infrastructure.gemini.image_analyzer import GeminiImageAnalyzer
        
        image_file = test_assets_path / "eiffel_tower.jpg"
        if not image_file.exists():
            pytest.skip(f"Изображение не найдено: {image_file}")
        
        analyzer = GeminiImageAnalyzer()
        
        start_time = time.perf_counter()
        result = analyzer.analyze(str(image_file))
        processing_time = (time.perf_counter() - start_time) * 1000
        
        inspection = MediaInspection(
            asset_path="eiffel_tower.jpg",
            asset_absolute_path=str(image_file),
            media_type="image",
            file_size_bytes=image_file.stat().st_size,
            surrounding_text_before="",
            surrounding_text_after="",
            system_prompt=analyzer.system_prompt if hasattr(analyzer, "system_prompt") else "",
            user_prompt="Analyze and describe this image.",
            model_name=getattr(analyzer, "model_name", "gemini-2.0-flash"),
            response_raw={"description": result.description} if result else None,
            response_parsed=result,
            final_chunk_content=f"[IMAGE: eiffel_tower.jpg]\n{result.description if result else 'N/A'}",
            processing_time_ms=processing_time,
        )
        
        if not pipeline_inspector.reports:
            pipeline_inspector.reports.append(
                InspectionReport(
                    file_path="real_media_test",
                    file_content_preview="",
                )
            )
        
        pipeline_inspector.add_media_inspection(inspection)
        
        assert result is not None
        assert result.description
    
    def test_real_audio_analysis(
        self,
        pipeline_inspector,
        test_assets_path: Path,
    ):
        """Реальный анализ аудио через Gemini Audio API."""
        from tests.e2e.audit.conftest import MediaInspection, InspectionReport
        from semantic_core.infrastructure.gemini.audio_analyzer import GeminiAudioAnalyzer
        
        audio_file = test_assets_path / "slides_ideas_audio.ogg"
        if not audio_file.exists():
            pytest.skip(f"Аудио не найдено: {audio_file}")
        
        analyzer = GeminiAudioAnalyzer()
        
        start_time = time.perf_counter()
        result = analyzer.analyze(str(audio_file))
        processing_time = (time.perf_counter() - start_time) * 1000
        
        inspection = MediaInspection(
            asset_path="slides_ideas_audio.ogg",
            asset_absolute_path=str(audio_file),
            media_type="audio",
            file_size_bytes=audio_file.stat().st_size,
            surrounding_text_before="",
            surrounding_text_after="",
            system_prompt=getattr(analyzer, "system_prompt", ""),
            user_prompt="Transcribe and analyze this audio.",
            model_name=getattr(analyzer, "model_name", "gemini-2.0-flash"),
            response_raw={
                "description": result.description if result else "",
                "transcription": result.transcription if result else "",
            },
            response_parsed=result,
            final_chunk_content=f"[AUDIO]\n{result.transcription if result else 'N/A'}",
            processing_time_ms=processing_time,
        )
        
        if not pipeline_inspector.reports:
            pipeline_inspector.reports.append(
                InspectionReport(
                    file_path="real_media_test",
                    file_content_preview="",
                )
            )
        
        pipeline_inspector.add_media_inspection(inspection)
        
        assert result is not None


# ============================================================================
# Тест всех медиа файлов в папке
# ============================================================================


class TestMediaInventory:
    """Инвентаризация всех медиа-файлов в tests/asests/."""
    
    def test_list_all_media_files(self, test_assets_path: Path):
        """Выводит список всех медиа-файлов для визуальной проверки."""
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        audio_extensions = {".mp3", ".ogg", ".wav", ".m4a"}
        video_extensions = {".mp4", ".webm", ".mov", ".avi"}
        
        media_files = {
            "images": [],
            "audio": [],
            "video": [],
        }
        
        for file in test_assets_path.iterdir():
            if file.is_file():
                ext = file.suffix.lower()
                if ext in image_extensions:
                    media_files["images"].append(file.name)
                elif ext in audio_extensions:
                    media_files["audio"].append(file.name)
                elif ext in video_extensions:
                    media_files["video"].append(file.name)
        
        # Проверяем что есть хотя бы какие-то медиа-файлы
        total = sum(len(v) for v in media_files.values())
        assert total > 0, "В tests/asests/ нет медиа-файлов"
        
        # Проверяем конкретные файлы которые мы ожидаем
        assert "cat_photo.png" in media_files["images"], "Нет cat_photo.png"
        assert "slides_ideas_audio.ogg" in media_files["audio"], "Нет slides_ideas_audio.ogg"
