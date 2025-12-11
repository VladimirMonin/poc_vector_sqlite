"""
Fixtures для тестов CLI модуля.

Обеспечивает изоляцию тестов от реальных ENV переменных
(GEMINI_API_KEY, OPENAI_API_KEY и т.д.) и .env файла.
"""

import os
from functools import wraps
from pathlib import Path
from unittest.mock import patch

import pytest


def _isolated_semantic_config_init(original_init):
    """Обёртка для SemanticConfig.__init__ которая отключает чтение .env."""
    @wraps(original_init)
    def wrapper(self, **kwargs):
        # Принудительно отключаем чтение .env файла
        if "_env_file" not in kwargs:
            kwargs["_env_file"] = None
        return original_init(self, **kwargs)
    return wrapper


@pytest.fixture(autouse=True)
def isolate_env_for_config_tests(monkeypatch):
    """Изолирует тесты от реальных API ключей в окружении и .env файла.
    
    1. Удаляет переменные окружения которые могут повлиять на SemanticConfig
    2. Патчит SemanticConfig чтобы он НЕ читал .env файл
    
    Это autouse фикстура - применяется автоматически ко всем тестам в папке.
    """
    # Список переменных для удаления
    env_vars_to_remove = [
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "OLLAMA_HOST",
    ]
    
    # Удаляем конкретные ключи
    for var in env_vars_to_remove:
        monkeypatch.delenv(var, raising=False)
    
    # Удаляем все SEMANTIC_* переменные
    semantic_vars = [k for k in os.environ if k.startswith("SEMANTIC_")]
    for var in semantic_vars:
        monkeypatch.delenv(var, raising=False)
    
    # Патчим SemanticConfig.__init__ чтобы он не читал .env
    from semantic_core.config import SemanticConfig
    original_init = SemanticConfig.__init__
    
    monkeypatch.setattr(
        SemanticConfig,
        "__init__",
        _isolated_semantic_config_init(original_init)
    )
    
    yield
