# 🔍 Phase 13.5 — Context Window для расширения контекста чанков

**Статус:** 📋 СПЕЦИФИКАЦИЯ  
**Приоритет:** 🟡 ВАЖНО (после 13.3 и 13.4)  
**Цель:** Добавить возможность загружать соседние чанки для улучшения контекста

---

## 1. Проблема

### 1.1 Симптом: "Дед с деменцией"

RAG-чат находит релевантный чанк, но ответ неполный:

```
User: "Расскажи про функции в Python"

Найден чанк:
  "Функции позволяют организовать код в переиспользуемые блоки."

Ответ LLM:
  "Функции позволяют организовать код. К сожалению, у меня нет 
   дополнительной информации о функциях в предоставленном контексте."
```

**Проблема:** Следующий чанк содержит примеры кода, но он не подгружен!

### 1.2 Текущие режимы

| Режим | Что делает | Проблема |
|-------|------------|----------|
| `full_docs=False` | Только найденные чанки | Мало контекста |
| `full_docs=True` | Весь документ целиком | Слишком много токенов |

**Нужен промежуточный вариант!**

---

## 2. Решение: `context_window`

### 2.1 Концепция

```
Документ: [chunk_0] [chunk_1] [chunk_2] [chunk_3] [chunk_4]
                              ↑
                        найден (score=0.95)

context_window=0 → [chunk_2]                           # только найденный
context_window=1 → [chunk_1, chunk_2, chunk_3]         # ±1 сосед
context_window=2 → [chunk_0, chunk_1, chunk_2, chunk_3, chunk_4]  # ±2 соседа
```

### 2.2 Для медиа с таймкодами

```
Видео "lecture.mp4" (60 минут, 12 чанков по 5 минут):

  [0] 00:00-05:00 Введение
  [1] 05:00-10:00 Основы Python      ← найден по запросу "переменные"
  [2] 10:00-15:00 Функции
  [3] 15:00-20:00 Классы
  ...

context_window=0 → только [05:00-10:00]
context_window=1 → [00:00-05:00, 05:00-10:00, 10:00-15:00]
```

### 2.3 Сравнение с альтернативами

| Подход | Токенов | Релевантность | Контроль |
|--------|---------|---------------|----------|
| `context_window=0` | ~500 | ⭐⭐⭐⭐⭐ | ✓ |
| `context_window=1` | ~1500 | ⭐⭐⭐⭐ | ✓ |
| `context_window=2` | ~2500 | ⭐⭐⭐ | ✓ |
| `full_docs=True` | ~10000+ | ⭐⭐ | ✗ |
| `expand_to_siblings` | Переменно | ⭐⭐⭐ | ✗ |

---

## 3. Архитектура изменений

### 3.1 Интерфейс `BaseVectorStore`

**Файл:** `semantic_core/interfaces/vector_store.py`

```python
@abstractmethod
def get_sibling_chunks(
    self, 
    chunk_id: int, 
    window: int = 1,
) -> list[Chunk]:
    """Получить соседние чанки того же документа.
    
    Возвращает чанки в диапазоне позиций [position - window, position + window],
    отсортированные по chunk_index.
    
    Args:
        chunk_id: ID центрального чанка.
        window: Количество соседей в каждую сторону.
    
    Returns:
        Список чанков, включая центральный.
        
    Example:
        >>> store.get_sibling_chunks(chunk_id=5, window=1)
        [Chunk(index=1), Chunk(index=2), Chunk(index=3)]  # center=2
    """
```

### 3.2 Реализация в `PeeweeVectorStore`

**Файл:** `semantic_core/infrastructure/storage/peewee/adapter.py`

```python
def get_sibling_chunks(self, chunk_id: int, window: int = 1) -> list[Chunk]:
    """Получить соседние чанки."""
    try:
        center = ChunkModel.get_by_id(chunk_id)
    except ChunkModel.DoesNotExist:
        return []
    
    doc_id = center.document_id
    position = center.chunk_index
    
    # Запрос соседей
    siblings = (ChunkModel
        .select()
        .where(ChunkModel.document == doc_id)
        .where(ChunkModel.chunk_index.between(
            position - window, 
            position + window
        ))
        .order_by(ChunkModel.chunk_index))
    
    return [self._chunk_model_to_chunk(s) for s in siblings]
```

### 3.3 Метод в `SemanticCore`

**Файл:** `semantic_core/pipeline.py`

```python
def search_chunks(
    self,
    query: str,
    filters: Optional[dict] = None,
    limit: int = 10,
    mode: str = "hybrid",
    k: int = 60,
    chunk_type_filter: Optional[str] = None,
    context_window: int = 0,  # NEW!
) -> list[ChunkResult]:
    """Гранулярный поиск по чанкам.
    
    Args:
        ...
        context_window: Количество соседних чанков в каждую сторону.
            0 = только найденные чанки (по умолчанию).
            1 = найденный + по 1 соседу с каждой стороны.
            2 = найденный + по 2 соседа с каждой стороны.
    """
    results = self.store.search_chunks(...)
    
    if context_window > 0:
        results = self._expand_with_context(results, context_window)
    
    return results


def _expand_with_context(
    self, 
    results: list[ChunkResult], 
    window: int,
) -> list[ChunkResult]:
    """Расширяет результаты соседними чанками.
    
    Дедуплицирует чанки (если соседи пересекаются).
    Сохраняет оригинальные скоры для найденных чанков.
    """
    seen_ids: set[int] = set()
    expanded: list[ChunkResult] = []
    
    for result in results:
        siblings = self.store.get_sibling_chunks(result.chunk_id, window)
        
        for sibling in siblings:
            if sibling.id in seen_ids:
                continue
            seen_ids.add(sibling.id)
            
            # Если это оригинальный результат — сохраняем скор
            if sibling.id == result.chunk_id:
                expanded.append(result)
            else:
                # Соседи получают скор 0 (контекст, не результат)
                expanded.append(ChunkResult(
                    chunk_id=sibling.id,
                    content=sibling.content,
                    chunk_type=sibling.chunk_type,
                    score=0.0,
                    match_type=MatchType.CONTEXT,  # Новый тип!
                    parent_doc_id=result.parent_doc_id,
                    metadata=sibling.metadata,
                ))
    
    return expanded
```

### 3.4 Новый `MatchType.CONTEXT`

**Файл:** `semantic_core/domain/search_result.py`

```python
class MatchType(str, Enum):
    """Тип совпадения в поиске."""
    VECTOR = "vector"
    FTS = "fts"
    HYBRID = "hybrid"
    CONTEXT = "context"  # NEW: Соседний чанк (не результат поиска)
```

### 3.5 RAGEngine

**Файл:** `semantic_core/core/rag.py`

```python
def ask(
    self,
    query: str,
    limit: int = 5,
    mode: str = "hybrid",
    full_docs: bool = False,
    context_window: int = 0,  # NEW!
) -> RAGResponse:
    """Отвечает на вопрос с контекстом из базы.
    
    Args:
        ...
        context_window: Количество соседних чанков (игнорируется при full_docs=True).
    """
    if full_docs:
        sources = self.core.search(...)
        context = self._build_full_docs_context(sources)
    else:
        sources = self.core.search_chunks(
            query=query,
            limit=limit,
            mode=mode,
            context_window=context_window,  # Передаём!
        )
        context = self._build_chunks_context(sources)
```

### 3.6 CLI

**Файл:** `semantic_core/cli/commands/search.py`

```python
def search(
    query: str = typer.Argument(...),
    limit: int = typer.Option(10, "--limit", "-l"),
    mode: str = typer.Option("hybrid", "--mode", "-m"),
    context: int = typer.Option(0, "--context", "-c",
        help="Соседние чанки в каждую сторону (0=только найденные)"),
):
```

**Файл:** `semantic_core/cli/commands/chat.py`

```python
def chat(
    ...
    context_window: int = typer.Option(0, "--context-window", "-cw",
        help="Соседние чанки для каждого результата"),
):
```

---

## 4. Примеры использования

### 4.1 CLI

```bash
# Поиск с контекстом
semantic search "функции python" --context 1

# Чат с расширенным контекстом
semantic chat --context-window 2

# Чат с полными документами (существующий)
semantic chat --full-docs
```

### 4.2 API

```python
from semantic_core import SemanticCore

core = SemanticCore(...)

# Только найденные чанки
results = core.search_chunks("функции", context_window=0)

# С соседями
results = core.search_chunks("функции", context_window=1)

# RAG с контекстом
from semantic_core.core import RAGEngine

rag = RAGEngine(core=core, llm=llm)
response = rag.ask("Что такое функции?", context_window=1)
```

---

## 5. Тест-кейсы

### 5.1 Unit-тесты

```python
class TestGetSiblingChunks:
    """Тесты получения соседних чанков."""
    
    def test_window_0_returns_only_center(self, store):
        """window=0 возвращает только центральный чанк."""
        siblings = store.get_sibling_chunks(chunk_id=5, window=0)
        assert len(siblings) == 1
    
    def test_window_1_returns_three_chunks(self, store):
        """window=1 возвращает 3 чанка (если есть соседи)."""
        siblings = store.get_sibling_chunks(chunk_id=5, window=1)
        assert len(siblings) == 3
    
    def test_edge_chunk_returns_fewer(self, store):
        """Первый/последний чанк возвращает меньше соседей."""
        # chunk_id=0 — первый в документе
        siblings = store.get_sibling_chunks(chunk_id=0, window=1)
        assert len(siblings) == 2  # только center + next
    
    def test_sorted_by_index(self, store):
        """Чанки отсортированы по chunk_index."""
        siblings = store.get_sibling_chunks(chunk_id=5, window=2)
        indices = [s.chunk_index for s in siblings]
        assert indices == sorted(indices)


class TestSearchWithContext:
    """Тесты поиска с context_window."""
    
    def test_context_window_expands_results(self, core):
        """context_window добавляет соседние чанки."""
        results_0 = core.search_chunks("query", context_window=0)
        results_1 = core.search_chunks("query", context_window=1)
        
        assert len(results_1) >= len(results_0)
    
    def test_context_chunks_have_zero_score(self, core):
        """Соседние чанки имеют score=0."""
        results = core.search_chunks("query", context_window=1)
        
        context_chunks = [r for r in results if r.match_type == MatchType.CONTEXT]
        for chunk in context_chunks:
            assert chunk.score == 0.0
    
    def test_no_duplicate_chunks(self, core):
        """Нет дубликатов при пересечении соседей."""
        results = core.search_chunks("query", context_window=2)
        
        chunk_ids = [r.chunk_id for r in results]
        assert len(chunk_ids) == len(set(chunk_ids))
```

---

## 6. Миграция и совместимость

### 6.1 Обратная совместимость

- `context_window=0` — поведение по умолчанию, ничего не меняется
- `full_docs=True` — продолжает работать
- Все существующие тесты проходят

### 6.2 Deprecation

Не требуется — это новая функциональность.

---

## 7. Критерии приёмки

- [ ] `store.get_sibling_chunks(chunk_id, window)` реализован
- [ ] `core.search_chunks(..., context_window=N)` работает
- [ ] `rag.ask(..., context_window=N)` работает
- [ ] CLI `--context` / `--context-window` добавлены
- [ ] `MatchType.CONTEXT` добавлен
- [ ] Unit-тесты проходят
- [ ] Документация обновлена

---

## 8. Оценка трудозатрат

| Компонент | Часы |
|-----------|------|
| `get_sibling_chunks` в adapter | 1 |
| `_expand_with_context` в pipeline | 2 |
| RAGEngine интеграция | 1 |
| CLI флаги | 0.5 |
| Unit-тесты | 2 |
| Документация | 0.5 |
| **Итого** | **~7 часов** |

---

## 9. Ссылки

- **Проблема контекста:** обсуждение в Phase 13.2
- **RAGEngine:** `semantic_core/core/rag.py`
- **VectorStore:** `semantic_core/interfaces/vector_store.py`
- **Adapter:** `semantic_core/infrastructure/storage/peewee/adapter.py`
