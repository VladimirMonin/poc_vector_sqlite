# Phase 15.2: Local Embeddings — Sentence Transformers

**Статус:** TODO  
**Ответственный:** Agent 2  
**Длительность:** 3-4 дня  
**Зависимости:** Phase 15.0 (Interface Contracts) ✅

---

## 🎯 Цель

Реализовать `SentenceTransformerEmbedder` — провайдер локальных эмбеддингов через `sentence-transformers`, альтернатива `GeminiEmbedder`. Поддержка моделей для английского, русского и мультиязычных эмбеддингов.

**Экономия:** 100% стоимости vs Gemini Embeddings API (локальные эмбеддинги бесплатны).

---

## 📦 Что Нужно Реализовать

### 1. **Основной Класс: `SentenceTransformerEmbedder`**

**Файл:** `semantic_core/infrastructure/local/sentence_transformer_embedder.py`

```python
from semantic_core.interfaces import BaseEmbedder
from typing import List, Literal
from sentence_transformers import SentenceTransformer

class SentenceTransformerEmbedder(BaseEmbedder):
    """
    Локальные эмбеддинги через sentence-transformers.
    
    Attributes:
        model_name: Название модели (all-MiniLM-L6-v2, paraphrase-multilingual-mpnet-base-v2, etc.)
        device: cpu/cuda
        normalize: Нормализовать векторы (для косинусного сходства)
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Literal["cpu", "cuda"] = "cpu",
        normalize: bool = True
    ):
        # Загрузить модель sentence-transformers
        # Логирование через semantic logger
        pass
    
    @property
    def dimension(self) -> int:
        """Размерность эмбеддингов модели"""
        pass
    
    @property
    def max_tokens(self) -> int:
        """Максимальная длина токенов модели"""
        pass
    
    def embed(self, text: str) -> List[float]:
        """Получить эмбеддинг для одного текста"""
        pass
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Получить эмбеддинги для батча текстов (эффективнее)"""
        pass
```

**Требования:**

- ✅ Наследует `BaseEmbedder` из `semantic_core/interfaces/embedder.py`
- ✅ Реализует свойства `dimension` и `max_tokens`
- ✅ Реализует методы `embed()` и `embed_batch()`
- ✅ Поддерживает `normalize=True` (для косинусного сходства в SQLite)
- ✅ Обрабатывает ошибки: CUDA недоступна, модель не найдена
- ✅ Логирование через `semantic_core.utils.logger` (bind model_name, device)

---

### 2. **Рекомендуемые Модели**

| Модель | Размерность | Язык | Качество | Скорость |
|--------|-------------|------|----------|----------|
| `all-MiniLM-L6-v2` | 384 | EN | ⭐⭐⭐ | 🚀🚀🚀 |
| `all-mpnet-base-v2` | 768 | EN | ⭐⭐⭐⭐ | 🚀🚀 |
| `paraphrase-multilingual-mpnet-base-v2` | 768 | Multilingual | ⭐⭐⭐⭐ | 🚀🚀 |
| `sentence-transformers/LaBSE` | 768 | 109 языков | ⭐⭐⭐⭐⭐ | 🚀 |

**Рекомендация для проекта:**

- **Русский текст:** `paraphrase-multilingual-mpnet-base-v2`
- **Английский текст:** `all-mpnet-base-v2`
- **Быстрая разработка:** `all-MiniLM-L6-v2` (самая быстрая)

---

### 3. **Конфигурация (опционально)**

Добавить в `semantic_core/config.py`:

```python
class SentenceTransformerConfig(BaseModel):
    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"
    normalize: bool = True
    cache_folder: Optional[str] = None  # Где хранить скачанные модели
```

---

## ✅ Checklist Самопроверки

Перед отправкой на Code Review убедись:

### **Код:**

- [ ] `SentenceTransformerEmbedder` наследует `BaseEmbedder`
- [ ] `dimension` возвращает корректную размерность модели
- [ ] `max_tokens` возвращает корректный лимит модели
- [ ] `embed()` возвращает `List[float]` правильной длины
- [ ] `embed_batch()` эффективнее множественных вызовов `embed()`
- [ ] `normalize=True` корректно нормализует векторы (L2 norm)
- [ ] Обработка ошибок с информативными сообщениями
- [ ] Логирование: загрузка модели, embedding batch size, время (с эмодзи 🧠)
- [ ] Код следует стилю проекта (docstrings, type hints)

### **Производительность:**

- [ ] Модель загружается один раз (кэшируется)
- [ ] Поддержка GPU (`device='cuda'`) если доступна
- [ ] Батчинг работает эффективно (не вызывает OOM)
- [ ] Нет утечек памяти при длительной работе

### **Документация:**

- [ ] Docstrings для класса и методов
- [ ] Примеры использования в комментариях
- [ ] Таблица рекомендуемых моделей с характеристиками

---

## 🧪 Список Тестов

### **Unit Tests** (`tests/unit/infrastructure/local/test_sentence_transformer_embedder.py`)

```python
import pytest
from semantic_core.infrastructure.local import SentenceTransformerEmbedder
from semantic_core.interfaces import BaseEmbedder

class TestSentenceTransformerEmbedder:
    """Unit тесты для SentenceTransformerEmbedder"""
    
    def test_embedder_initialization(self):
        """Проверка инициализации с разными параметрами"""
        embedder = SentenceTransformerEmbedder(
            model_name="all-MiniLM-L6-v2",
            device="cpu"
        )
        assert embedder.model_name == "all-MiniLM-L6-v2"
        assert embedder.device == "cpu"
    
    def test_embed_single_text(self):
        """Проверка эмбеддинга одного текста"""
        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        embedding = embedder.embed("Semantic search example")
        
        assert isinstance(embedding, list)
        assert len(embedding) == embedder.dimension
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embed_batch_texts(self):
        """Проверка батчинга"""
        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        texts = [
            "First document",
            "Second document",
            "Third document"
        ]
        embeddings = embedder.embed_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(emb) == embedder.dimension for emb in embeddings)
    
    def test_dimension_property_matches_model(self):
        """Проверка что dimension совпадает с реальной размерностью"""
        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        
        # all-MiniLM-L6-v2 имеет 384 размерности
        assert embedder.dimension == 384
        
        # Проверка через реальный эмбеддинг
        embedding = embedder.embed("test")
        assert len(embedding) == embedder.dimension
    
    def test_max_tokens_property(self):
        """Проверка свойства max_tokens"""
        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        
        # all-MiniLM-L6-v2 имеет max_seq_length 256
        assert embedder.max_tokens > 0
        assert isinstance(embedder.max_tokens, int)
    
    def test_model_loading_caching(self):
        """Проверка что модель загружается один раз"""
        embedder = SentenceTransformerEmbedder(model_name="all-MiniLM-L6-v2")
        
        # Первый эмбеддинг
        emb1 = embedder.embed("First text")
        
        # Второй эмбеддинг - модель НЕ должна загружаться повторно
        emb2 = embedder.embed("Second text")
        
        assert len(emb1) == len(emb2)
    
    def test_device_selection_cpu(self):
        """Проверка работы на CPU"""
        embedder = SentenceTransformerEmbedder(device="cpu")
        embedding = embedder.embed("CPU test")
        assert len(embedding) == embedder.dimension
    
    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_device_selection_cuda(self):
        """Проверка работы на GPU (если доступен)"""
        embedder = SentenceTransformerEmbedder(device="cuda")
        embedding = embedder.embed("GPU test")
        assert len(embedding) == embedder.dimension
    
    def test_normalize_embeddings(self):
        """Проверка нормализации векторов"""
        embedder = SentenceTransformerEmbedder(normalize=True)
        embedding = embedder.embed("Normalize test")
        
        # Проверка L2 нормы (должна быть ~1.0)
        import numpy as np
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 0.01  # Допуск на погрешность
    
    def test_no_normalize(self):
        """Проверка что без нормализации векторы не нормализованы"""
        embedder = SentenceTransformerEmbedder(normalize=False)
        embedding = embedder.embed("No normalize test")
        
        import numpy as np
        norm = np.linalg.norm(embedding)
        assert norm != 1.0  # Не нормализован
    
    def test_different_models(self):
        """Проверка загрузки разных моделей"""
        models = [
            ("all-MiniLM-L6-v2", 384),
            ("all-mpnet-base-v2", 768)
        ]
        
        for model_name, expected_dim in models:
            embedder = SentenceTransformerEmbedder(model_name=model_name)
            assert embedder.dimension == expected_dim
    
    def test_interface_compliance(self):
        """Проверка соответствия интерфейсу BaseEmbedder"""
        embedder = SentenceTransformerEmbedder()
        assert isinstance(embedder, BaseEmbedder)
        assert hasattr(embedder, "dimension")
        assert hasattr(embedder, "max_tokens")
        assert hasattr(embedder, "embed")
        assert hasattr(embedder, "embed_batch")
    
    def test_embedding_consistency(self):
        """Проверка что одинаковый текст даёт одинаковый эмбеддинг"""
        embedder = SentenceTransformerEmbedder()
        
        emb1 = embedder.embed("Consistency test")
        emb2 = embedder.embed("Consistency test")
        
        # Должны быть идентичны
        import numpy as np
        assert np.allclose(emb1, emb2, rtol=1e-5)
    
    def test_empty_text_handling(self):
        """Проверка обработки пустого текста"""
        embedder = SentenceTransformerEmbedder()
        
        # Пустая строка должна вернуть валидный эмбеддинг
        embedding = embedder.embed("")
        assert len(embedding) == embedder.dimension
    
    def test_long_text_truncation(self):
        """Проверка что длинный текст обрезается до max_tokens"""
        embedder = SentenceTransformerEmbedder()
        
        # Создаём очень длинный текст
        long_text = "word " * 1000  # Гораздо больше max_tokens
        
        # Не должно быть ошибки, текст обрезается
        embedding = embedder.embed(long_text)
        assert len(embedding) == embedder.dimension
    
    def test_batch_vs_single_consistency(self):
        """Проверка что batch даёт те же результаты что и single"""
        embedder = SentenceTransformerEmbedder()
        texts = ["First", "Second", "Third"]
        
        # Батчем
        batch_embeddings = embedder.embed_batch(texts)
        
        # По одному
        single_embeddings = [embedder.embed(text) for text in texts]
        
        # Должны совпадать
        import numpy as np
        for batch_emb, single_emb in zip(batch_embeddings, single_embeddings):
            assert np.allclose(batch_emb, single_emb, rtol=1e-5)
```

---

## 📊 Acceptance Criteria

**Phase 15.2 считается завершённой, если:**

1. ✅ Все unit тесты проходят (минимум 16 тестов)
2. ✅ `SentenceTransformerEmbedder` корректно наследует `BaseEmbedder`
3. ✅ Свойства `dimension` и `max_tokens` корректны
4. ✅ Эмбеддинги работают на CPU и GPU (если доступен)
5. ✅ Батчинг эффективнее одиночных вызовов
6. ✅ Нормализация векторов работает корректно
7. ✅ Обработка ошибок с понятными сообщениями
8. ✅ Логирование через semantic logger
9. ✅ Код следует стилю проекта (docstrings, type hints)

---

## 📝 Дополнительные Задачи (Опционально)

Если останется время:

- [ ] Benchmark: сравнение скорости разных моделей
- [ ] Benchmark: сравнение качества retrieval (Recall@K) с Gemini
- [ ] Поддержка кастомных моделей (загрузка из локальной папки)
- [ ] Кэширование эмбеддингов (SQLite cache)
- [ ] Поддержка `quantization` для экономии памяти

---

## 🚀 Начало Работы

1. Создай ветку: `git checkout -b phase_15.2_local_embeddings`
2. Установи зависимости: `pip install sentence-transformers`
3. Изучи интерфейс: `semantic_core/interfaces/embedder.py`
4. Посмотри пример: `semantic_core/infrastructure/gemini/embedder.py` (как Gemini это делает)
5. Создай файл: `semantic_core/infrastructure/local/sentence_transformer_embedder.py`
6. Напиши тесты: `tests/unit/infrastructure/local/test_sentence_transformer_embedder.py`
7. Запусти тесты: `pytest tests/unit/infrastructure/local/ -v`
8. Сделай коммиты (формат: `phase 15.2 feat: ...`)

---

## 📚 Полезные Ссылки

- **Sentence Transformers:** <https://www.sbert.net/>
- **Model Hub:** <https://huggingface.co/models?library=sentence-transformers>
- **Pretrained Models:** <https://www.sbert.net/docs/pretrained_models.html>
- **Context7 (для документации):** `/UKPLab/sentence-transformers`

---

**Удачи! 🧠**  
_Координатор Phase 15_
