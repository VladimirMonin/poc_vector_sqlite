"""Integration тесты для ComponentFactory.

Проверяют реальное создание компонентов с ленивыми импортами.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from semantic_core.core.factory import ComponentFactory
from semantic_core.config import SemanticConfig, DefaultsConfig


class TestComponentFactoryIntegration:
    """Integration тесты создания компонентов через фабрику."""

    def test_create_embedder_google_real_import(self, tmp_path):
        """Фабрика создаёт GeminiEmbedder с реальным импортом."""
        # Arrange
        config = SemanticConfig(
            db_path=tmp_path / "test.db",
            defaults=DefaultsConfig(embedding_provider="gemini"),
            gemini_api_key="test_key",
        )

        # Act
        embedder = ComponentFactory.create_embedder(config)

        # Assert
        from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder

        assert isinstance(embedder, GeminiEmbedder)
        assert embedder.dimension == 768

    def test_create_llm_google_real_import(self, tmp_path):
        """Фабрика создаёт GeminiLLMProvider с реальным импортом."""
        # Arrange
        config = SemanticConfig(
            db_path=tmp_path / "test.db",
            defaults=DefaultsConfig(llm_provider="gemini"),
            gemini_api_key="test_key",
        )

        # Act
        llm = ComponentFactory.create_llm(config)

        # Assert
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        assert isinstance(llm, GeminiLLMProvider)

    def test_create_embedder_local_missing_dependencies(self, tmp_path):
        """Без local dependencies → понятная ошибка с hint."""
        # Arrange
        config = SemanticConfig(
            db_path=tmp_path / "test.db",
            defaults=DefaultsConfig(embedding_provider="local"),
        )

        # Act & Assert
        with pytest.raises(ImportError) as exc_info:
            ComponentFactory.create_embedder(config)

        error_msg = str(exc_info.value)
        assert "dependencies not installed" in error_msg.lower()
        assert "pip install" in error_msg.lower()

    def test_create_transcriber_whisper_real_import_or_graceful_error(self, tmp_path):
        """Whisper: либо создаёт компонент, либо даёт понятную ошибку, либо возвращает None (disabled)."""
        # Arrange
        config = SemanticConfig(
            db_path=tmp_path / "test.db",
            defaults=DefaultsConfig(transcriber_provider="whisper"),
        )

        # Act
        try:
            transcriber = ComponentFactory.create_transcriber(config)

            # Если получилось создать — проверяем тип
            if transcriber is not None:
                from semantic_core.infrastructure.local.whisper import (
                    WhisperTranscriber,
                )

                assert isinstance(transcriber, WhisperTranscriber)
            else:
                # Фабрика вернула None (disabled) — это нормально
                assert True

        except ImportError as e:
            # Если нет зависимостей — проверяем hint
            error_msg = str(e)
            assert "dependencies not installed" in error_msg.lower()
            assert "pip install" in error_msg.lower()

    def test_create_semantic_core_with_google_providers(self, tmp_path):
        """Создание компонентов с Google провайдерами."""
        # Arrange
        db_path = tmp_path / "test.db"
        config = SemanticConfig(
            db_path=db_path,
            defaults=DefaultsConfig(
                embedding_provider="gemini",
                llm_provider="gemini",
            ),
            gemini_api_key="test_key",
        )

        # Act - создаём компоненты по отдельности
        embedder = ComponentFactory.create_embedder(config)
        llm = ComponentFactory.create_llm(config)

        # Assert
        from semantic_core.infrastructure.gemini.embedder import GeminiEmbedder
        from semantic_core.infrastructure.llm.gemini import GeminiLLMProvider

        assert isinstance(embedder, GeminiEmbedder)
        assert isinstance(llm, GeminiLLMProvider)
