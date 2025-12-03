# Phase 10.1: Миграция на gemini-embedding-001

## Статус: PLANNING

## Контекст

Phase 10 обнаружила критическую проблему: **модель `text-embedding-004` НЕ поддерживает Batch API**.

Google Batch API (`asyncBatchEmbedContent`) работает только с моделью `gemini-embedding-001`.

## Исследование качества моделей

### Тест на практических примерах

Сравнение качества на 4-х текстах с 3-мя запросами:

| Запрос | text-embedding-004 (768) | gemini-embedding-001 (768) | Разница |
|--------|--------------------------|----------------------------|---------|
| SQL оптимизация | 0.5905 | 0.6727 | **+14%** |
| Кэширование | 0.4770 | 0.5069 | **+6%** |
| Безопасность | 0.5614 | 0.6205 | **+10%** |

### Вывод о качестве

**`gemini-embedding-001` при 768 измерениях показывает на 6-14% ЛУЧШИЕ результаты** чем `text-embedding-004`.

Это объясняется:
1. Более новая архитектура модели
2. MRL (Matryoshka Representation Learning) — специально обученная на уменьшенную размерность
3. Google оптимизировал модель именно для такого использования

### MRL — Matryoshka Representation Learning

`gemini-embedding-001` по умолчанию генерирует 3072 измерения, но поддерживает MRL:
- 3072 dim → полное качество (100%)
- 768 dim → ~98% качества (практически без потерь)
- 256 dim → ~94% качества

**Рекомендация:** использовать 768 измерений — экономия места x4 при потере качества всего 2%.

## Критическая проблема совместимости

### Эмбеддинги моделей НЕСОВМЕСТИМЫ

```
Cross-model similarity: -0.05 (случайный шум)
```

**Векторы от `text-embedding-004` и `gemini-embedding-001` НЕЛЬЗЯ смешивать в одной БД!**

Это означает: при переходе нужна **полная переиндексация всех данных**.

## Масштаб миграции

### Затронутые файлы (17 файлов)

```
semantic_core/embeddings.py              - DEFAULT_MODEL
semantic_core/config.py                  - default_model в SemanticConfig
semantic_core/pipeline.py                - параметр model_name
semantic_core/services.py                - model_name
semantic_core/batch_manager.py           - BatchManager
semantic_core/infrastructure/gemini/embedder.py - GeminiEmbedder
tests/e2e/gemini/test_real_batch.py      - E2E тест
tests/integration/...                    - integration тесты
config.py                                - конфигурация проекта
example_phase5.py                        - пример использования
doc/architecture/...                     - документация
```

### Места использования

```
~17 файлов с "text-embedding-004"
~63 ссылки на dimension=768
```

## План миграции

### Вариант A: Breaking Change (рекомендуется)

**Полная замена на `gemini-embedding-001`**

Плюсы:
- Одна модель везде (sync/async/batch)
- Лучшее качество (+10% в среднем)
- 50% экономия через Batch API
- Простота кодовой базы

Минусы:
- Требует полной переиндексации
- Breaking change для пользователей

### Вариант B: Dual-Model Support

**Поддержка обеих моделей параллельно**

Плюсы:
- Обратная совместимость
- Постепенная миграция

Минусы:
- Сложность кодовой базы
- Два пути эмбеддинга
- Путаница для пользователей

### Рекомендация

**Выбрать Вариант A** — проект в активной разработке, пользователей мало, качество важнее совместимости.

## Checklist миграции

### Код

- [ ] Заменить DEFAULT_MODEL на "gemini-embedding-001" в embeddings.py
- [ ] Обновить config.py SemanticConfig defaults
- [ ] Обновить GeminiEmbedder default model
- [ ] Обновить pipeline.py default model
- [ ] Обновить services.py default model
- [ ] Добавить параметр output_dimensionality в sync embeddings
- [ ] Проверить/обновить BatchManager defaults

### Тесты

- [ ] Обновить E2E тесты
- [ ] Обновить integration тесты
- [ ] Добавить тест MRL (проверка 768 vs 3072)
- [ ] Проверить backward compatibility (отсутствие старых дефолтов)

### Документация

- [ ] Обновить README.md (модель)
- [ ] Обновить doc/architecture/01_embeddings_basics.md
- [ ] Обновить doc/architecture/02_gemini_api.md
- [ ] Добавить Migration Guide
- [ ] Обновить changelog

### Миграция данных

- [ ] Написать скрипт переиндексации
- [ ] Документировать процесс миграции
- [ ] Добавить CLI команду для переиндексации

## Технические детали

### Новые параметры API

```python
# Sync embedding с MRL
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=["text"],
    config={
        "task_type": "RETRIEVAL_DOCUMENT",
        "output_dimensionality": 768,  # MRL!
    }
)
```

### Batch API (уже реализовано в Phase 10)

```python
# batching.py уже использует gemini-embedding-001
client = GeminiBatchClient(
    api_key=api_key,
    model_name="models/gemini-embedding-001",
    dimension=768,
)
```

## Экономический эффект

| Модель | Метод | Цена (1M токенов) |
|--------|-------|-------------------|
| text-embedding-004 | sync | $0.00 (бесплатно) |
| gemini-embedding-001 | sync | ~$0.001 |
| gemini-embedding-001 | batch | ~$0.0005 (**50% скидка**) |

При больших объёмах Batch API даёт существенную экономию.

## Риски

1. **Переиндексация** — может занять время на больших датасетах
2. **Временный downtime** — поиск не будет работать во время миграции
3. **Изменение релевантности** — результаты поиска изменятся (к лучшему, но изменятся)

## Следующие шаги

1. ✅ E2E тест Batch API с gemini-embedding-001 (Phase 10 DONE)
2. ⏳ Решение о варианте миграции (A или B)
3. ⏳ Реализация миграции
4. ⏳ Документация и changelog
5. ⏳ Major version bump (если breaking change)

## Приоритет

**MEDIUM** — Batch API работает с новой моделью, но sync embeddings всё ещё используют старую. Это создаёт несовместимость, которую нужно решить.
