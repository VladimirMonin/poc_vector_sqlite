"""
Tests for SemanticConfig — централизованная конфигурация библиотеки.

Тестируем:
- Дефолтные значения
- Загрузку из TOML-файла
- Переменные окружения
- Приоритет: env > toml > defaults
- Синглтон и reset_config()
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from semantic_core.config import (
    SemanticConfig,
    get_config,
    reset_config,
    find_config_file,
)


class TestSemanticConfigDefaults:
    """Тесты дефолтных значений SemanticConfig."""

    def test_default_db_path(self):
        """db_path имеет дефолтное значение."""
        config = SemanticConfig()
        assert config.db_path == Path("semantic.db")

    def test_default_gemini_api_key_none(self):
        """gemini_api_key по умолчанию None."""
        config = SemanticConfig()
        assert config.gemini_api_key is None

    def test_default_splitter(self):
        """splitter имеет корректный дефолт."""
        config = SemanticConfig()
        assert config.splitter == "smart"

    def test_default_context_strategy(self):
        """context_strategy имеет корректный дефолт."""
        config = SemanticConfig()
        assert config.context_strategy == "hierarchical"

    def test_default_media_enabled(self):
        """media_enabled по умолчанию True."""
        config = SemanticConfig()
        assert config.media_enabled is True
        assert config.media_rpm_limit == 15

    def test_default_search_config(self):
        """Настройки поиска имеют корректные дефолты."""
        config = SemanticConfig()
        assert config.search_limit == 10
        assert config.search_type == "hybrid"

    def test_default_log_level(self):
        """log_level имеет корректный дефолт."""
        config = SemanticConfig()
        assert config.log_level == "INFO"
        assert config.log_file is None


class TestSemanticConfigFromToml:
    """Тесты загрузки конфигурации из TOML файла."""

    def test_load_from_toml_database_section(self):
        """Секция [database] загружается корректно."""
        toml_content = """
[database]
path = "custom.db"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    assert config.db_path == Path("custom.db")
            finally:
                os.unlink(f.name)

    def test_load_from_toml_gemini_section(self):
        """Секция [gemini] загружается корректно."""
        toml_content = """
[gemini]
api_key = "test-api-key-123"
model = "custom-embedding"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    assert config.gemini_api_key == "test-api-key-123"
                    assert config.embedding_model == "custom-embedding"
            finally:
                os.unlink(f.name)

    def test_load_from_toml_processing_section(self):
        """Секция [processing] загружается корректно."""
        toml_content = """
[processing]
splitter = "simple"
context_strategy = "basic"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    assert config.splitter == "simple"
                    assert config.context_strategy == "basic"
            finally:
                os.unlink(f.name)

    def test_load_from_toml_media_section(self):
        """Секция [media] загружается корректно."""
        toml_content = """
[media]
enabled = false
rpm_limit = 30
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    assert config.media_enabled is False
                    assert config.media_rpm_limit == 30
            finally:
                os.unlink(f.name)

    def test_load_from_toml_search_section(self):
        """Секция [search] загружается корректно."""
        toml_content = """
[search]
limit = 20
type = "vector"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    assert config.search_limit == 20
                    assert config.search_type == "vector"
            finally:
                os.unlink(f.name)

    def test_load_from_toml_logging_section(self):
        """Секция [logging] загружается корректно."""
        toml_content = """
[logging]
level = "DEBUG"
file = "app.log"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()
                    assert config.log_level == "DEBUG"
                    assert config.log_file == Path("app.log")
            finally:
                os.unlink(f.name)


class TestSemanticConfigEnvVars:
    """Тесты загрузки из переменных окружения."""

    def test_env_var_semantic_db_path(self):
        """SEMANTIC_DB_PATH загружается из env."""
        with patch.dict(os.environ, {"SEMANTIC_DB_PATH": "env.db"}):
            with patch("semantic_core.config.find_config_file", return_value=None):
                reset_config()
                config = get_config()
                assert config.db_path == Path("env.db")
                reset_config()

    def test_env_var_semantic_log_level(self):
        """SEMANTIC_LOG_LEVEL загружается из env."""
        with patch.dict(os.environ, {"SEMANTIC_LOG_LEVEL": "WARNING"}):
            with patch("semantic_core.config.find_config_file", return_value=None):
                reset_config()
                config = get_config()
                assert config.log_level == "WARNING"
                reset_config()

    def test_direct_override_gemini_api_key(self):
        """gemini_api_key можно передать напрямую."""
        with patch("semantic_core.config.find_config_file", return_value=None):
            config = SemanticConfig(gemini_api_key="direct-key")
            assert config.gemini_api_key == "direct-key"


class TestSemanticConfigPriority:
    """Тесты приоритета: kwargs > toml > defaults."""

    def test_kwargs_override_toml(self):
        """Прямые аргументы имеют приоритет над TOML."""
        toml_content = """
[database]
path = "toml.db"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig(db_path="override.db")
                    # kwargs должны победить
                    assert config.db_path == Path("override.db")
            finally:
                os.unlink(f.name)

    def test_toml_overrides_defaults(self):
        """TOML имеет приоритет над дефолтами."""
        toml_content = """
[database]
path = "toml.db"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                # Чистим env от SEMANTIC_ переменных
                clean_env = {k: v for k, v in os.environ.items() if not k.startswith("SEMANTIC_")}
                with patch.dict(os.environ, clean_env, clear=True):
                    with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                        config = SemanticConfig()
                        assert config.db_path == Path("toml.db")
            finally:
                os.unlink(f.name)


class TestFindConfigFile:
    """Тесты функции find_config_file."""

    def test_find_semantic_toml_in_cwd(self):
        """Находит semantic.toml в текущей директории."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "semantic.toml"
            config_path.write_text("[database]\npath = 'test.db'\n")

            found = find_config_file(start_dir=Path(tmpdir))
            assert found == config_path

    def test_returns_none_if_no_config(self):
        """Возвращает None если конфиг не найден."""
        with tempfile.TemporaryDirectory() as tmpdir:
            found = find_config_file(start_dir=Path(tmpdir))
            assert found is None

    def test_searches_parent_directories(self):
        """Ищет в родительских директориях."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir)
            child = parent / "subdir"
            child.mkdir()
            
            config_path = parent / "semantic.toml"
            config_path.write_text("[database]\npath = 'test.db'\n")

            found = find_config_file(start_dir=child)
            assert found == config_path


class TestGetConfigSingleton:
    """Тесты синглтона get_config() и reset_config()."""

    def test_get_config_returns_same_instance(self):
        """get_config() возвращает один и тот же объект."""
        with patch("semantic_core.config.find_config_file", return_value=None):
            reset_config()
            config1 = get_config()
            config2 = get_config()
            assert config1 is config2
            reset_config()

    def test_reset_config_clears_singleton(self):
        """reset_config() сбрасывает синглтон."""
        with patch("semantic_core.config.find_config_file", return_value=None):
            reset_config()
            config1 = get_config()
            reset_config()
            config2 = get_config()
            # Это разные объекты (хотя с одинаковыми значениями)
            assert config1 is not config2
            reset_config()


class TestConfigValidators:
    """Тесты валидаторов конфигурации."""

    def test_db_path_string_converted_to_path(self):
        """Строка преобразуется в Path."""
        config = SemanticConfig(db_path="custom.db")
        assert isinstance(config.db_path, Path)
        assert config.db_path == Path("custom.db")

    def test_api_key_whitespace_stripped(self):
        """Пробелы убираются из API ключа."""
        config = SemanticConfig(gemini_api_key="  my-key  ")
        assert config.gemini_api_key == "my-key"

    def test_empty_api_key_becomes_none(self):
        """Пустая строка API ключа становится None."""
        config = SemanticConfig(gemini_api_key="")
        assert config.gemini_api_key is None

    def test_require_api_key_raises_without_key(self):
        """require_api_key() выбрасывает исключение без ключа."""
        config = SemanticConfig()
        with pytest.raises(ValueError, match="GEMINI_API_KEY not configured"):
            config.require_api_key()

    def test_require_api_key_returns_key(self):
        """require_api_key() возвращает ключ если он есть."""
        config = SemanticConfig(gemini_api_key="my-key")
        assert config.require_api_key() == "my-key"

    def test_to_toml_dict_excludes_secrets(self):
        """to_toml_dict() не включает API ключи."""
        config = SemanticConfig(gemini_api_key="secret-key")
        toml_dict = config.to_toml_dict()
        
        # api_key не должен быть в gemini секции
        assert "api_key" not in toml_dict.get("gemini", {})
        # Но модель должна быть
        assert "model" in toml_dict.get("gemini", {})


class TestSemanticConfigFullToml:
    """Тесты полной загрузки из TOML."""

    def test_load_full_config_file(self):
        """Полный TOML файл загружается корректно."""
        toml_content = """
# Semantic Core Configuration

[database]
path = "my_semantic.db"

[gemini]
api_key = "my-gemini-key"
batch_key = "my-batch-key"
model = "text-embedding-004"
embedding_dimension = 512

[processing]
splitter = "simple"
context_strategy = "basic"

[media]
enabled = false
rpm_limit = 25

[search]
limit = 15
type = "fts"

[logging]
level = "DEBUG"
file = "semantic.log"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write(toml_content)
            f.flush()

            try:
                with patch("semantic_core.config.find_config_file", return_value=Path(f.name)):
                    config = SemanticConfig()

                    # Database
                    assert config.db_path == Path("my_semantic.db")

                    # Gemini
                    assert config.gemini_api_key == "my-gemini-key"
                    assert config.gemini_batch_key == "my-batch-key"
                    assert config.embedding_model == "text-embedding-004"
                    assert config.embedding_dimension == 512

                    # Processing
                    assert config.splitter == "simple"
                    assert config.context_strategy == "basic"

                    # Media
                    assert config.media_enabled is False
                    assert config.media_rpm_limit == 25

                    # Search
                    assert config.search_limit == 15
                    assert config.search_type == "fts"

                    # Logging
                    assert config.log_level == "DEBUG"
                    assert config.log_file == Path("semantic.log")

            finally:
                os.unlink(f.name)
