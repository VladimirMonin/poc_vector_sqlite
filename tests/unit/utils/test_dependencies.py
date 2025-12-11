"""Unit-тесты для utils.dependencies (Phase 15.5).

Тесты проверяют функции проверки доступности провайдеров
и генерации install hints.
"""

import pytest
from unittest.mock import patch

from semantic_core.utils.dependencies import (
    check_google_available,
    check_openai_available,
    check_local_embeddings_available,
    check_local_whisper_available,
    check_media_available,
    get_available_providers,
    get_missing_providers,
    get_install_hint,
    require_provider,
    _is_apple_silicon,
)


class TestCheckProviders:
    """Тесты функций проверки доступности провайдеров."""

    def test_check_google_available_when_installed(self):
        """Google SDK доступен."""
        # Предполагаем что в тестовом окружении Google SDK установлен
        is_available, error = check_google_available()

        # Если установлен → должно быть True
        # Если нет → тест пропускаем (зависит от окружения)
        if is_available:
            assert error is None
        else:
            assert "No module named" in error

    def test_check_openai_available(self):
        """OpenAI SDK может быть или не быть установлен."""
        is_available, error = check_openai_available()

        # Проверяем только что возвращает правильный тип
        assert isinstance(is_available, bool)
        if not is_available:
            assert isinstance(error, str)

    def test_check_media_available(self):
        """Media libs могут быть или не быть установлены."""
        is_available, error = check_media_available()

        assert isinstance(is_available, bool)
        if not is_available:
            assert isinstance(error, str)


class TestGetProviders:
    """Тесты функций получения списка провайдеров."""

    def test_get_available_providers(self):
        """Возвращает dict с всеми провайдерами."""
        providers = get_available_providers()

        assert isinstance(providers, dict)
        assert "google" in providers
        assert "openai" in providers
        assert "local_embeddings" in providers
        assert "local_whisper" in providers
        assert "media" in providers

        # Все значения должны быть bool
        for value in providers.values():
            assert isinstance(value, bool)

    def test_get_missing_providers(self):
        """Возвращает список отсутствующих провайдеров."""
        missing = get_missing_providers()

        assert isinstance(missing, list)
        # Может быть пустым если все установлены
        for provider in missing:
            assert isinstance(provider, str)


class TestInstallHints:
    """Тесты генерации install hints."""

    def test_get_install_hint_google(self):
        """Google hint."""
        hint = get_install_hint("google")

        assert "pip install" in hint
        assert "google" in hint

    def test_get_install_hint_openai(self):
        """OpenAI hint."""
        hint = get_install_hint("openai")

        assert "pip install" in hint
        assert "openai" in hint

    @patch("semantic_core.utils.dependencies._is_apple_silicon", return_value=True)
    def test_get_install_hint_local_embeddings_mlx(self, mock_is_apple):
        """Local embeddings на Apple Silicon → MLX."""
        hint = get_install_hint("local_embeddings")

        assert "pip install" in hint
        assert "local-embeddings-mlx" in hint

    @patch("semantic_core.utils.dependencies._is_apple_silicon", return_value=False)
    def test_get_install_hint_local_embeddings_cpu(self, mock_is_apple):
        """Local embeddings на CPU → sentence-transformers."""
        hint = get_install_hint("local_embeddings")

        assert "pip install" in hint
        assert "local-embeddings]" in hint

    def test_get_install_hint_unknown(self):
        """Неизвестный провайдер → generic hint."""
        hint = get_install_hint("unknown")

        assert "pip install" in hint
        assert "unknown" in hint


class TestRequireProvider:
    """Тесты require_provider."""

    def test_require_provider_installed(self):
        """Провайдер установлен → не выбрасывает ошибку."""
        # Google должен быть установлен в тестовом окружении
        # Если нет → тест упадёт, что ожидаемо
        try:
            require_provider("google", "Test feature")
        except ImportError:
            pytest.skip("Google SDK not installed in test environment")

    def test_require_provider_not_installed(self):
        """Провайдер не установлен → выбрасывает ImportError."""
        # Патчим проверку чтобы симулировать отсутствие
        with patch(
            "semantic_core.utils.dependencies.check_openai_available",
            return_value=(False, "No module named 'openai'"),
        ):
            with pytest.raises(ImportError, match="dependencies not installed"):
                require_provider("openai", "Test OpenAI feature")

    def test_require_provider_unknown(self):
        """Неизвестный провайдер → ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            require_provider("unknown_provider")


class TestPlatformDetection:
    """Тесты определения платформы."""

    def test_is_apple_silicon(self):
        """Определение Apple Silicon."""
        result = _is_apple_silicon()

        assert isinstance(result, bool)
        # На реальном Apple Silicon должно быть True
        # На других платформах — False
