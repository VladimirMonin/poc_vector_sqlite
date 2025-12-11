# Phase 15.3: OpenAI LLM Provider — Альтернатива Gemini для RAG

**Статус:** TODO  
**Ответственный:** Agent 3  
**Длительность:** 3-4 дня  
**Зависимости:** Phase 15.0 (Interface Contracts) ✅

---

## 🎯 Цель

Реализовать `OpenAILLMProvider` — провайдер для генерации ответов через OpenAI API, альтернатива `GeminiLLMProvider`. Поддержка моделей GPT-4o, GPT-4o-mini, GPT-3.5-turbo для RAG системы.

**Преимущества:** Более стабильные API, лучшая документация, опциональная альтернатива Gemini.

---

## 📦 Что Нужно Реализовать

### 1. **Основной Класс: `OpenAILLMProvider`**

**Файл:** `semantic_core/infrastructure/llm/openai_llm.py`

```python
from semantic_core.interfaces import ILLMProvider
from typing import List, Dict, Optional, Iterator
from openai import OpenAI

class OpenAILLMProvider(ILLMProvider):
    """
    OpenAI LLM провайдер для RAG.
    
    Attributes:
        model: gpt-4o / gpt-4o-mini / gpt-3.5-turbo
        api_key: OpenAI API ключ
        temperature: 0.0-2.0 (креативность)
        max_tokens: Максимум токенов в ответе
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        # Инициализация OpenAI клиента
        # Логирование через semantic logger
        pass
    
    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Сгенерировать ответ на промпт.
        
        Args:
            prompt: Пользовательский запрос
            system_message: Системный промпт (инструкции для модели)
            **kwargs: Дополнительные параметры (temperature, max_tokens)
        
        Returns:
            Сгенерированный текст
        """
        pass
    
    def generate_stream(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Iterator[str]:
        """
        Стриминг ответа (опционально).
        
        Yields:
            Чанки текста по мере генерации
        """
        pass
    
    def count_tokens(self, text: str) -> int:
        """
        Подсчёт токенов в тексте (для оценки стоимости).
        
        Uses tiktoken library.
        """
        pass
```

**Требования:**

- ✅ Реализует интерфейс `ILLMProvider` (если он существует, иначе создай на основе `GeminiLLMProvider`)
- ✅ Поддерживает `system_message` для RAG промптов
- ✅ Реализует `generate()` для синхронной генерации
- ✅ Реализует `generate_stream()` для streaming (опционально, но желательно)
- ✅ Реализует `count_tokens()` через `tiktoken`
- ✅ Обрабатывает ошибки: rate limits, invalid API key, timeout
- ✅ Логирование через `semantic_core.utils.logger` (bind model, tokens, cost)

---

### 2. **Интерфейс `ILLMProvider` (если ещё не создан)**

**Файл:** `semantic_core/interfaces/llm.py`

```python
from abc import ABC, abstractmethod
from typing import Optional, Iterator

class ILLMProvider(ABC):
    """Интерфейс для LLM провайдеров (Gemini, OpenAI, etc.)"""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs
    ) -> str:
        """Сгенерировать ответ на промпт"""
        pass
    
    def generate_stream(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs
    ) -> Iterator[str]:
        """Стриминг ответа (опционально)"""
        raise NotImplementedError("Streaming not supported")
    
    def count_tokens(self, text: str) -> int:
        """Подсчёт токенов для оценки стоимости"""
        raise NotImplementedError("Token counting not supported")
```

**Примечание:** Проверь существует ли уже `ILLMProvider` в `semantic_core/interfaces/`. Если нет — создай. Если есть — используй существующий.

---

### 3. **Рекомендуемые Модели**

| Модель | Context Window | Стоимость (1M tokens) | Качество | Скорость |
|--------|----------------|----------------------|----------|----------|
| `gpt-4o` | 128k | $2.50 / $10.00 | ⭐⭐⭐⭐⭐ | 🚀🚀 |
| `gpt-4o-mini` | 128k | $0.15 / $0.60 | ⭐⭐⭐⭐ | 🚀🚀🚀 |
| `gpt-3.5-turbo` | 16k | $0.50 / $1.50 | ⭐⭐⭐ | 🚀🚀🚀 |

**Рекомендация для проекта:**

- **Production RAG:** `gpt-4o-mini` (лучший баланс цена/качество)
- **Высокое качество:** `gpt-4o`
- **Быстрая разработка:** `gpt-3.5-turbo` (дешевле всего)

---

### 4. **Конфигурация (опционально)**

Добавить в `semantic_core/config.py`:

```python
class OpenAIConfig(BaseModel):
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 30  # seconds
```

---

## ✅ Checklist Самопроверки

Перед отправкой на Code Review убедись:

### **Код:**

- [ ] `OpenAILLMProvider` реализует `ILLMProvider`
- [ ] `generate()` корректно обрабатывает `system_message`
- [ ] `generate_stream()` работает (если реализован)
- [ ] `count_tokens()` использует `tiktoken` для точного подсчёта
- [ ] Обработка ошибок: rate limits, invalid API key, timeout, network errors
- [ ] Retry logic для rate limits (exponential backoff)
- [ ] Логирование: prompt tokens, completion tokens, total cost (с эмодзи 💬)
- [ ] Код следует стилю проекта (docstrings, type hints)

### **Производительность:**

- [ ] API ключ загружается из переменной окружения `OPENAI_API_KEY`
- [ ] Timeout настраивается (default 30 секунд)
- [ ] Нет блокировок при streaming

### **Документация:**

- [ ] Docstrings для класса и методов
- [ ] Примеры использования в комментариях
- [ ] Таблица моделей с характеристиками и стоимостью
- [ ] Инструкции по получению API ключа

---

## 🧪 Список Тестов

### **Unit Tests** (`tests/unit/infrastructure/llm/test_openai_llm.py`)

```python
import pytest
from semantic_core.infrastructure.llm import OpenAILLMProvider
from semantic_core.interfaces import ILLMProvider
from unittest.mock import Mock, patch

class TestOpenAILLMProvider:
    """Unit тесты для OpenAILLMProvider"""
    
    def test_llm_initialization(self):
        """Проверка инициализации с разными параметрами"""
        llm = OpenAILLMProvider(
            model="gpt-4o-mini",
            api_key="test-key",
            temperature=0.5
        )
        assert llm.model == "gpt-4o-mini"
        assert llm.temperature == 0.5
    
    @patch("openai.OpenAI")
    def test_generate_response(self, mock_openai):
        """Проверка генерации ответа"""
        # Mock OpenAI response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        llm = OpenAILLMProvider(api_key="test-key")
        response = llm.generate("Test prompt")
        
        assert response == "Test response"
        mock_client.chat.completions.create.assert_called_once()
    
    @patch("openai.OpenAI")
    def test_generate_with_system_message(self, mock_openai):
        """Проверка использования system_message"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Response"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        llm = OpenAILLMProvider(api_key="test-key")
        llm.generate(
            prompt="User question",
            system_message="You are a helpful assistant"
        )
        
        # Проверка что system message передан
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant"
        assert messages[1]["role"] == "user"
    
    @patch("openai.OpenAI")
    def test_streaming_support(self, mock_openai):
        """Проверка streaming генерации"""
        mock_client = Mock()
        
        # Mock streaming response
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content="Hello"))]),
            Mock(choices=[Mock(delta=Mock(content=" world"))]),
            Mock(choices=[Mock(delta=Mock(content="!"))])
        ]
        mock_client.chat.completions.create.return_value = iter(mock_chunks)
        mock_openai.return_value = mock_client
        
        llm = OpenAILLMProvider(api_key="test-key")
        chunks = list(llm.generate_stream("Test prompt"))
        
        assert chunks == ["Hello", " world", "!"]
    
    def test_token_counting(self):
        """Проверка подсчёта токенов через tiktoken"""
        llm = OpenAILLMProvider(model="gpt-4o-mini")
        
        text = "Hello, how are you?"
        token_count = llm.count_tokens(text)
        
        assert token_count > 0
        assert isinstance(token_count, int)
    
    def test_token_counting_different_models(self):
        """Проверка что tiktoken использует правильный encoding для модели"""
        llm_gpt4 = OpenAILLMProvider(model="gpt-4o")
        llm_gpt35 = OpenAILLMProvider(model="gpt-3.5-turbo")
        
        text = "Test tokenization"
        
        tokens_gpt4 = llm_gpt4.count_tokens(text)
        tokens_gpt35 = llm_gpt35.count_tokens(text)
        
        # Должны быть примерно одинаковыми (но могут отличаться)
        assert abs(tokens_gpt4 - tokens_gpt35) <= 2
    
    @patch("openai.OpenAI")
    def test_error_handling_invalid_api_key(self, mock_openai):
        """Проверка обработки неправильного API ключа"""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("Invalid API key")
        mock_openai.return_value = mock_client
        
        llm = OpenAILLMProvider(api_key="invalid-key")
        
        with pytest.raises(Exception, match="Invalid API key"):
            llm.generate("Test prompt")
    
    @patch("openai.OpenAI")
    def test_error_handling_rate_limit(self, mock_openai):
        """Проверка обработки rate limits"""
        from openai import RateLimitError
        
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = RateLimitError("Rate limit exceeded")
        mock_openai.return_value = mock_client
        
        llm = OpenAILLMProvider(api_key="test-key")
        
        with pytest.raises(RateLimitError):
            llm.generate("Test prompt")
    
    @patch("openai.OpenAI")
    def test_temperature_parameter(self, mock_openai):
        """Проверка передачи параметра temperature"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Response"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        llm = OpenAILLMProvider(api_key="test-key", temperature=0.2)
        llm.generate("Test prompt")
        
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.2
    
    @patch("openai.OpenAI")
    def test_max_tokens_parameter(self, mock_openai):
        """Проверка передачи параметра max_tokens"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Response"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        llm = OpenAILLMProvider(api_key="test-key", max_tokens=1000)
        llm.generate("Test prompt")
        
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["max_tokens"] == 1000
    
    def test_interface_compliance(self):
        """Проверка соответствия интерфейсу ILLMProvider"""
        llm = OpenAILLMProvider(api_key="test-key")
        assert isinstance(llm, ILLMProvider)
        assert hasattr(llm, "generate")
        assert hasattr(llm, "generate_stream")
        assert hasattr(llm, "count_tokens")
    
    @patch("openai.OpenAI")
    def test_different_models(self, mock_openai):
        """Проверка работы с разными моделями"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Response"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        models = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
        
        for model in models:
            llm = OpenAILLMProvider(model=model, api_key="test-key")
            llm.generate("Test")
            
            call_args = mock_client.chat.completions.create.call_args
            assert call_args.kwargs["model"] == model
    
    def test_api_key_from_env(self):
        """Проверка загрузки API ключа из переменной окружения"""
        import os
        
        # Сохранить старое значение
        old_key = os.environ.get("OPENAI_API_KEY")
        
        try:
            os.environ["OPENAI_API_KEY"] = "env-test-key"
            llm = OpenAILLMProvider()  # Без явного api_key
            
            # Должен использовать ключ из env
            assert llm.api_key == "env-test-key" or llm.client.api_key == "env-test-key"
        finally:
            # Восстановить старое значение
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
            else:
                os.environ.pop("OPENAI_API_KEY", None)
```

---

## 📊 Acceptance Criteria

**Phase 15.3 считается завершённой, если:**

1. ✅ Все unit тесты проходят (минимум 13 тестов)
2. ✅ `OpenAILLMProvider` корректно реализует `ILLMProvider`
3. ✅ `generate()` работает с system_message
4. ✅ `generate_stream()` работает (опционально, но желательно)
5. ✅ `count_tokens()` использует tiktoken
6. ✅ Обработка ошибок: rate limits, invalid API key
7. ✅ Retry logic для rate limits
8. ✅ Логирование через semantic logger (токены, стоимость)
9. ✅ Код следует стилю проекта (docstrings, type hints)

---

## 📝 Дополнительные Задачи (Опционально)

Если останется время:

- [ ] Поддержка function calling (для RAG с инструментами)
- [ ] Кэширование ответов (SQLite cache для идентичных промптов)
- [ ] Benchmark: сравнение качества RAG с Gemini (RAGAS metrics)
- [ ] Поддержка `response_format="json_object"` для структурированных ответов
- [ ] Async версия (`async def generate()`)

---

## 🚀 Начало Работы

1. Создай ветку: `git checkout -b phase_15.3_openai_llm`
2. Установи зависимости: `pip install openai tiktoken`
3. Проверь интерфейс: `semantic_core/interfaces/llm.py` (создай если нет)
4. Посмотри пример: `semantic_core/infrastructure/llm/gemini_llm.py` (если существует)
5. Создай файл: `semantic_core/infrastructure/llm/openai_llm.py`
6. Напиши тесты: `tests/unit/infrastructure/llm/test_openai_llm.py`
7. Запусти тесты: `pytest tests/unit/infrastructure/llm/ -v`
8. Сделай коммиты (формат: `phase 15.3 feat: ...`)

---

## 📚 Полезные Ссылки

- **OpenAI Python SDK:** <https://github.com/openai/openai-python>
- **API Reference:** <https://platform.openai.com/docs/api-reference>
- **Tiktoken:** <https://github.com/openai/tiktoken>
- **Pricing:** <https://openai.com/api/pricing/>
- **Context7 (для документации):** `/openai/openai-python`

---

**Удачи! 💬**  
_Координатор Phase 15_
