# Phase 10.1: Миграция на gemini-embedding-001

## 📋 Исследование (выполнено)

### Проблема с Batch API

1. **Batch API для embeddings** работает **только** с `gemini-embedding-001`
2. `text-embedding-004` **НЕ поддерживает** `asyncBatchEmbedContent`
3. Метод `batches.create()` — для generative моделей (generateContent)
4. Метод `batches.create_embeddings()` — для embedding моделей

### Сравнение моделей

| Характеристика | text-embedding-004 | gemini-embedding-001 |
|----------------|-------------------|---------------------|
| Default dimension | 768 | 3072 |
| MRL support | Да | Да (768, 1536, 3072) |
| MTEB Score | 66.1 | **68.32** (+3.4%) |
| Batch API | ❌ НЕТ | ✅ ДА |
| Цена Batch | — | **50% скидка** |

### Качество при уменьшении размерности (gemini-001)

| Dimension | MTEB Score | Потеря |
|-----------|------------|--------|
| 3072 | 68.16 | — |
| 1536 | 68.17 | 0% |
| 768 | 67.99 | **-0.25%** |

### Практический тест retrieval quality

```
Query: "How to learn Python?"
  text-embedding-004 (768): Top1 score = 0.689
  gemini-001 (768):         Top1 score = 0.732 (+6.2%)
  gemini-001 (3072):        Top1 score = 0.747 (+8.4%)

Вывод: gemini-001 даже в 768 ЛУЧШЕ чем text-embedding-004!
```

### Совместимость моделей

⚠️ **КРИТИЧНО:** Векторы из разных моделей **НЕСОВМЕСТИМЫ**!

```
Cross-model similarity (одинаковый текст): -0.05
```

Нельзя смешивать embeddings из text-embedding-004 и gemini-embedding-001 в одной БД!

## 📂 Инвентаризация изменений

### Упоминания модели `text-embedding-004`

| Файл | Тип | Описание |
|------|-----|----------|
| `config.py` | Config | default embedding model |
| `semantic_core/config.py` | Config | SemanticConfig.embedding_model |
| `semantic_core/batch_manager.py` | Code | default model_name |
| `semantic_core/infrastructure/gemini/embedder.py` | Code | GeminiEmbedder default |
| `semantic_core/infrastructure/gemini/batching.py` | Code | GeminiBatchClient default |
| `semantic_core/cli/commands/init_cmd.py` | CLI | template config |
| `semantic_core/cli/commands/docs.py` | CLI | template config |
| `tests/unit/cli/test_config.py` | Test | config parsing test |
| `tests/unit/infrastructure/batching/test_jsonl_builder.py` | Test | model in test |
| `tests/e2e/gemini/test_real_batch.py` | Test | E2E test fixture |

### Упоминания dimension=768 (embedding-related)

| Файл | Количество | Описание |
|------|------------|----------|
| `config.py` | 2 | default dimension |
| `tests/conftest.py` | 1 | mock embedder |
| `tests/unit/infrastructure/batching/` | 5 | batch tests |
| `tests/integration/test_pipeline_media_enrichment.py` | 2 | mock vectors |
| `tests/integration/granular_search/` | 5 | mock vectors |
| `tests/integration/test_e2e_phase4.py` | 6 | mock vectors |
| `tests/test_phase_1_architecture.py` | 6 | mock vectors |
| `tests/test_phase_2_storage.py` | 10 | mock vectors |
| `tests/e2e/gemini/test_real_batch.py` | 6 | real API test |

**Примечание:** 768 в video/image тестах — это **пиксели**, не embedding dimension!

### Формат JSONL для Batch Embeddings

**Старый формат (для generative models):**
```json
{"key": "id", "request": {"model": "...", "contents": [...], "config": {...}}}
```

**Новый формат (для embeddings):**
```json
{"key": "id", "request": {"output_dimensionality": 768, "content": {"parts": [{"text": "..."}]}}}
```

Или использовать `inlined_requests` без файлов:
```python
client.batches.create_embeddings(
    model="gemini-embedding-001",
    src=types.EmbeddingsBatchJobSource(
        inlined_requests=types.EmbedContentBatch(
            contents=["text1", "text2", ...],
            config=types.EmbedContentConfig(output_dimensionality=768),
        ),
    ),
)
```

## ✅ План миграции

### Этап 1: Изменение defaults в конфигах

- [ ] `config.py` — изменить default на `gemini-embedding-001`
- [ ] `semantic_core/config.py` — изменить default
- [ ] `semantic_core/batch_manager.py` — изменить default
- [ ] `semantic_core/infrastructure/gemini/embedder.py` — изменить default
- [ ] `semantic_core/infrastructure/gemini/batching.py` — уже изменён на gemini-embedding-001

### Этап 2: CLI templates

- [ ] `semantic_core/cli/commands/init_cmd.py` — изменить template
- [ ] `semantic_core/cli/commands/docs.py` — изменить template

### Этап 3: Batch API implementation

- [ ] Использовать `batches.create_embeddings()` вместо `batches.create()`
- [ ] Использовать формат `inlined_requests` или file upload с правильным форматом
- [ ] Обновить `retrieve_results()` для нового формата ответа

### Этап 4: Тесты

- [ ] Обновить unit тесты с новым названием модели
- [ ] Обновить E2E тесты
- [ ] Запустить полный тест-сьют

### Этап 5: Документация

- [ ] Обновить README
- [ ] Обновить doc/architecture/

## ⚠️ Важные замечания

1. **Миграция существующих данных**: При смене модели ВСЕ существующие embeddings в БД становятся несовместимыми. Нужна полная переиндексация.

2. **768 dimensions остаётся**: Размерность 768 сохраняется, меняется только модель.

3. **Нормализация**: Для dimensions < 3072 нужна нормализация векторов (Google рекомендует).

4. **Цена**: Batch API даёт 50% скидку: $0.075 per 1M tokens vs $0.15 для sync.

## 📊 Оценка трудозатрат

| Задача | Время |
|--------|-------|
| Изменение defaults | 15 мин |
| Batch API fix | 30 мин |
| Тесты | 30 мин |
| E2E тест | 15 мин |
| **Итого** | **~1.5 часа** |
