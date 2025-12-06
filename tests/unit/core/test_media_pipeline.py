"""Unit-тесты для MediaPipeline — executor для step-based processing.

Архитектурный контекст:
-----------------------
Phase 14.1.0: Core Architecture — тесты для MediaPipeline executor.

Покрытие:
---------
- ✅ build_chunks() выполняет шаги по порядку
- ✅ should_run() пропускает шаги
- ✅ Обработка ошибок в опциональных vs критичных шагах
- ✅ register_step() добавление новых шагов
- ✅ Логирование выполнения
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from semantic_core.core.media_context import MediaContext
from semantic_core.core.media_pipeline import MediaPipeline
from semantic_core.domain import Chunk, Document, MediaType
from semantic_core.processing.steps.base import BaseProcessingStep, ProcessingStepError


class MockStep(BaseProcessingStep):
    """Mock processing step для тестов."""
    
    def __init__(
        self,
        name: str,
        add_chunks: int = 1,
        should_run_result: bool = True,
        raise_error: bool = False,
        is_optional: bool = False,
    ):
        self._name = name
        self.add_chunks = add_chunks
        self.should_run_result = should_run_result
        self.raise_error = raise_error
        self._is_optional = is_optional
        
        # Для отслеживания вызовов
        self.process_called = False
        self.should_run_called = False
    
    @property
    def step_name(self) -> str:
        return self._name
    
    @property
    def is_optional(self) -> bool:
        return self._is_optional
    
    def should_run(self, context: MediaContext) -> bool:
        self.should_run_called = True
        return self.should_run_result
    
    def process(self, context: MediaContext) -> MediaContext:
        self.process_called = True
        
        if self.raise_error:
            raise ProcessingStepError(
                step_name=self.step_name,
                message="Mock error",
            )
        
        # Создаём чанки
        chunks = [
            Chunk(
                content=f"{self.step_name} chunk {i}",
                chunk_index=context.base_index + i,
            )
            for i in range(self.add_chunks)
        ]
        
        return context.with_chunks(chunks)


@pytest.fixture
def base_context():
    """Базовый MediaContext для тестов."""
    return MediaContext(
        media_path=Path("test.mp3"),
        document=Document(content="Test", media_type=MediaType.TEXT),
        analysis={"type": "audio"},
        chunks=[],
        base_index=0,
    )


class TestMediaPipelineExecution:
    """Тесты для выполнения pipeline."""
    
    def test_executes_all_steps_in_order(self, base_context):
        """Проверяет выполнение всех шагов по порядку."""
        step1 = MockStep("step1", add_chunks=1)
        step2 = MockStep("step2", add_chunks=2)
        step3 = MockStep("step3", add_chunks=1)
        
        pipeline = MediaPipeline([step1, step2, step3])
        result = pipeline.build_chunks(base_context)
        
        # Все шаги выполнились
        assert step1.process_called
        assert step2.process_called
        assert step3.process_called
        
        # Чанки добавлены
        assert len(result.chunks) == 4  # 1 + 2 + 1
        assert result.base_index == 4
    
    def test_skips_steps_with_should_run_false(self, base_context):
        """Проверяет пропуск шагов с should_run=False."""
        step1 = MockStep("step1", should_run_result=True)
        step2 = MockStep("step2", should_run_result=False)  # Пропускаем
        step3 = MockStep("step3", should_run_result=True)
        
        pipeline = MediaPipeline([step1, step2, step3])
        result = pipeline.build_chunks(base_context)
        
        # step1 и step3 выполнились
        assert step1.process_called
        assert step3.process_called
        
        # step2 пропущен
        assert step2.should_run_called
        assert not step2.process_called
        
        # Чанки только от step1 и step3
        assert len(result.chunks) == 2
    
    def test_preserves_context_immutability(self, base_context):
        """Проверяет, что оригинальный context не изменяется."""
        step = MockStep("step1", add_chunks=1)
        pipeline = MediaPipeline([step])
        
        # Сохраняем оригинальные значения
        original_chunks = len(base_context.chunks)
        original_index = base_context.base_index
        
        result = pipeline.build_chunks(base_context)
        
        # Оригинал не изменился
        assert len(base_context.chunks) == original_chunks
        assert base_context.base_index == original_index
        
        # Результат обновлён
        assert len(result.chunks) > original_chunks
        assert result.base_index > original_index


class TestErrorHandling:
    """Тесты для обработки ошибок."""
    
    def test_optional_step_error_continues_pipeline(self, base_context):
        """Проверяет, что ошибка в опциональном шаге не останавливает pipeline."""
        step1 = MockStep("step1")
        step2 = MockStep("step2", raise_error=True, is_optional=True)
        step3 = MockStep("step3")
        
        pipeline = MediaPipeline([step1, step2, step3])
        
        # Не должно выбросить исключение
        result = pipeline.build_chunks(base_context)
        
        # step1 и step3 выполнились
        assert step1.process_called
        assert step3.process_called
        
        # step2 попытался выполниться
        assert step2.process_called
        
        # Чанки только от step1 и step3
        assert len(result.chunks) == 2
    
    def test_critical_step_error_stops_pipeline(self, base_context):
        """Проверяет, что ошибка в критичном шаге останавливает pipeline."""
        step1 = MockStep("step1")
        step2 = MockStep("step2", raise_error=True, is_optional=False)
        step3 = MockStep("step3")
        
        pipeline = MediaPipeline([step1, step2, step3])
        
        # Должно выбросить ProcessingStepError
        with pytest.raises(ProcessingStepError) as exc_info:
            pipeline.build_chunks(base_context)
        
        assert "step2" in str(exc_info.value)
        
        # step1 выполнился, step3 не выполнился
        assert step1.process_called
        assert not step3.process_called
    
    def test_unexpected_error_wrapped_in_processing_step_error(self, base_context):
        """Проверяет оборачивание неожиданных ошибок."""
        
        class BrokenStep(MockStep):
            def process(self, context: MediaContext) -> MediaContext:
                raise ValueError("Unexpected error")
        
        step = BrokenStep("broken", is_optional=False)
        pipeline = MediaPipeline([step])
        
        with pytest.raises(ProcessingStepError) as exc_info:
            pipeline.build_chunks(base_context)
        
        # Проверяем, что оригинальная ошибка сохранена
        assert exc_info.value.__cause__.__class__ == ValueError
        assert "broken" in str(exc_info.value)


class TestRegisterStep:
    """Тесты для register_step()."""
    
    def test_register_step_appends_by_default(self, base_context):
        """Проверяет добавление шага в конец."""
        step1 = MockStep("step1")
        pipeline = MediaPipeline([step1])
        
        step2 = MockStep("step2")
        pipeline.register_step(step2)
        
        assert len(pipeline.steps) == 2
        assert pipeline.steps[1] is step2
    
    def test_register_step_at_position(self, base_context):
        """Проверяет вставку шага на конкретную позицию."""
        step1 = MockStep("step1")
        step3 = MockStep("step3")
        pipeline = MediaPipeline([step1, step3])
        
        step2 = MockStep("step2")
        pipeline.register_step(step2, position=1)
        
        assert len(pipeline.steps) == 3
        assert pipeline.steps[0].step_name == "step1"
        assert pipeline.steps[1].step_name == "step2"
        assert pipeline.steps[2].step_name == "step3"


class TestLogging:
    """Тесты для логирования."""
    
    @patch("semantic_core.core.media_pipeline.logger")
    def test_logs_pipeline_start_and_completion(self, mock_logger, base_context):
        """Проверяет логирование старта и завершения."""
        step = MockStep("step1")
        pipeline = MediaPipeline([step])
        
        pipeline.build_chunks(base_context)
        
        # Проверяем вызовы logger.info
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        assert any("Starting media pipeline" in msg for msg in info_calls)
        assert any("Media pipeline completed" in msg for msg in info_calls)
    
    @patch("semantic_core.core.media_pipeline.logger")
    def test_logs_step_execution(self, mock_logger, base_context):
        """Проверяет логирование выполнения шагов."""
        step = MockStep("test_step", add_chunks=2)
        pipeline = MediaPipeline([step])
        
        pipeline.build_chunks(base_context)
        
        # Проверяем логирование шага
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        assert any("Step completed" in msg for msg in info_calls)
    
    @patch("semantic_core.core.media_pipeline.logger")
    def test_logs_optional_step_failure(self, mock_logger, base_context):
        """Проверяет логирование ошибок опциональных шагов."""
        step = MockStep("optional_step", raise_error=True, is_optional=True)
        pipeline = MediaPipeline([step])
        
        pipeline.build_chunks(base_context)
        
        # Проверяем warning для опционального шага
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        
        assert any("Optional step failed" in msg for msg in warning_calls)


class TestIntegration:
    """Интеграционные тесты."""
    
    def test_realistic_pipeline_with_summary_transcript_ocr(self, base_context):
        """Проверяет реалистичный сценарий: summary → transcript → ocr."""
        summary_step = MockStep("summary", add_chunks=1)
        transcript_step = MockStep("transcription", add_chunks=3)
        ocr_step = MockStep("ocr", add_chunks=2)
        
        pipeline = MediaPipeline([summary_step, transcript_step, ocr_step])
        result = pipeline.build_chunks(base_context)
        
        # Всего 6 чанков (1 + 3 + 2)
        assert len(result.chunks) == 6
        assert result.base_index == 6
        
        # Проверяем порядок
        assert result.chunks[0].content == "summary chunk 0"
        assert result.chunks[1].content == "transcription chunk 0"
        assert result.chunks[4].content == "ocr chunk 0"
