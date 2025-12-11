# Phase 17: Documentation Overhaul

> Масштабное обновление пользовательской документации после Phase 15-16

---

## 📦 Подфазы

| Подфаза | Название | Статус | Приоритет | Документ |
|---------|----------|--------|-----------|----------|
| **17.0** | Documentation Audit | ✅ Done | 🔥 Critical | [phase_17.0.md](phase_17.0.md) |
| **17.1** | Local Embeddings Docs | 📝 Planned | 🔥 Critical | [phase_17.1_local_embeddings_docs.md](phase_17.1_local_embeddings_docs.md) |
| **17.2** | Flask Integration Guide | 📝 Planned | 🔥 Critical | [phase_17.2_flask_integration.md](phase_17.2_flask_integration.md) |
| **17.3** | API Reference Updates | 📝 Planned | ⚠️ Important | [phase_17.3_api_reference_updates.md](phase_17.3_api_reference_updates.md) |
| **17.4** | Django Integration | 📌 Placeholder | 📌 Low | [phase_17.4_django_integration_placeholder.md](phase_17.4_django_integration_placeholder.md) |

---

## 🎯 Миссия фазы

**Проблема:**

После завершения Phase 15 (Multi-Provider Architecture) и Phase 16 (Debug Observatory) пользовательская документация (`docs/`) **критически устарела**.

**Разрыв между кодом и документацией:**

1. ❌ **ComponentFactory** не задокументирован (ключевой компонент Phase 15)
2. ❌ **LocalEmbedder** не упомянут в гайдах (Qwen3, BGE, MiniLM)
3. ❌ **Multi-provider конфигурация** поверхностно описана
4. ❌ **Flask integration** паттерн не задокументирован
5. ❌ **Debug Observatory** (`semantic inspect`) не попал в справочники
6. ❌ **Диаграммы** не отражают Phase 15-16 архитектуру

**Последствия:**

- Новые пользователи не знают про локальные модели (лучшая фича Phase 15)
- Невозможно интегрировать в веб-фреймворки без изучения кода
- Документация вводит в заблуждение (описывает старую архитектуру)

---

## 💡 Решение

### Phase 17.0: Documentation Audit ✅

**Завершено:** Детальный аудит 908 строк с выявлением:

- 14+ отсутствующих диаграмм (ComponentFactory, Observatory, multi-provider)
- Несоответствие кода и доков (OpenAI реализован, но помечен "potential")
- Устаревшие описания архитектуры

**Результат:** Техническое задание для Phase 17.1-17.4

---

### Phase 17.1: Local Embeddings Documentation 🔥

**Цель:** Актуализировать документацию локальных моделей.

**Что будет создано:**

1. **`docs/concepts/13_local_embeddings.md`** — концепция локальных моделей
   - MLX vs sentence-transformers
   - Выбор модели по hardware (Apple/CUDA/CPU)
   - MRL и dimension truncation

2. **`docs/guides/core/local-embeddings.md`** — практический гайд
   - Установка зависимостей
   - Конфигурация semantic.toml
   - Решение dimension mismatch (1024 vs 768)

3. **`docs/reference/local-models.md`** — справочник моделей
   - qwen3-embedding (1024D, 8K tokens)
   - all-minilm (384D, 512 tokens)
   - bge-small (384D, 512 tokens)
   - Comparison matrix (speed, quality, memory)

**Обновления:**

- `docs/concepts/11_multi_provider.md` — добавить Qwen3 в таблицы
- `docs/guides/extending/custom-embedder.md` — пример LocalEmbedder

**Критерий успеха:** Qwen3 упомянут в 5+ местах, новый пользователь может выбрать модель за 5 минут.

---

### Phase 17.2: Flask Integration Guide 🔥

**Цель:** Документировать интеграцию SemanticCore в Flask приложения.

**Workflow:**
1. **СНАЧАЛА:** Мигрировать код Flask app на Phase 15 архитектуру
2. **ПОТОМ:** Написать документацию

**Что будет обновлено в коде:**

1. `examples/flask_app/app/extensions.py` — ComponentFactory вместо hardcoded Gemini
2. `examples/flask_app/app/config.py` — интеграция SemanticConfig
3. `examples/flask_app/semantic.toml` — конфигурация с локальными моделями

**Что будет создано в docs:**

1. **`docs/guides/integrations/flask.md`** — полный гайд
   - Application Factory pattern
   - DI через app.extensions
   - Routes примеры (search, ingest, chat)
   - Production checklist

2. **Обновить `docs/guides/integrations/architecture.md`** — Flask паттерн
3. **Обновить `docs/guides/integrations/sync-nature.md`** — Flask sync/async

**Критерий успеха:** Flask app работает с локальными моделями, новый пользователь может интегрировать за 30 минут.

---

### Phase 17.3: API Reference Updates ⚠️

**Цель:** Детализировать справочную документацию.

**Что будет обновлено:**

1. **`docs/reference/interfaces.md`** — детальный API
   - Каждый метод: Parameters, Returns, Raises, Example
   - Конструкторы реализаций (GeminiEmbedder, LocalEmbedder)
   - Properties (dimension, max_tokens)

2. **`docs/reference/component-factory.md`** (NEW) — ComponentFactory API
   - create_embedder(), create_llm(), create_transcriber()
   - Graceful degradation
   - Convenience функция create_core()

3. **`docs/reference/configuration-options.md`** — детали providers.local
   - Все параметры LocalEmbedder
   - Примеры TOML конфигурации

**Критерий успеха:** Можно создать любой компонент без чтения исходного кода.

---

### Phase 17.4: Django Integration Placeholder 📌

**Статус:** Placeholder для будущего (Phase 18+)

**Цель:** Подготовить структуру для Django интеграции.

**Что будет создано:**

- Placeholder документ с draft планом
- Описание Django AppConfig pattern
- Сравнение Flask vs Django DI

**Когда начать:** После запроса на Django или Phase 18+

---

## 📊 Метрики успеха

### Полнота документации

- ✅ Qwen3-Embedding упомянут в concepts, guides, reference
- ✅ ComponentFactory полностью задокументирован
- ✅ Flask integration имеет рабочий пример + гайд
- ✅ API Reference детальный (конструкторы, параметры, raises)

### Актуальность

- ✅ Документация == код (нет разрыва)
- ✅ Все таблицы провайдеров актуальны
- ✅ Примеры кода протестированы

### Расширяемость

- ✅ Легко добавить новую локальную модель (структура готова)
- ✅ Легко добавить Django integration (паттерн заложен)
- ✅ Легко добавить новый провайдер (шаблон есть)

---

## 🔗 Связанные фазы

| Фаза | Отношение | Статус |
|------|-----------|--------|
| Phase 15 | Реализация multi-provider | ✅ Done |
| Phase 16 | Debug Observatory | ✅ Done |
| **Phase 17** | **Документация 15-16** | **🚧 In Progress** |
| Phase 18+ | Новые провайдеры/модели | 📌 Future |

---

## 🎨 Принципы документации

### Согласованность с архитектурным сериалом

- `doc/architecture/` — детальные технические статьи (для разработчиков)
- `docs/` — практические гайды (для пользователей)

**Разделение:**

| Тип | Где | Для кого |
|-----|-----|----------|
| Архитектурные решения | doc/architecture/ | Контрибьюторы |
| Концепции | docs/concepts/ | Advanced пользователи |
| Гайды | docs/guides/ | Все пользователи |
| Справочники | docs/reference/ | Quick lookup |

### Стиль (из 00_documentation_style_guide.md)

1. **Минимум кода, максимум объяснений**
   - Не дублировать код из репо
   - Фокус на паттернах и концептах

2. **Таблицы для сравнения**
   - Модели, провайдеры, фреймворки
   - Чёткие критерии выбора

3. **Практические примеры**
   - Реальные use cases
   - Типичные ошибки и решения

4. **Связанные ресурсы**
   - Ссылки между документами
   - Ссылки на архитектурный сериал

---

## 📅 Временная оценка

| Подфаза | Оценка | Зависимости |
|---------|--------|--------------|
| 17.0 Audit | 1 день | ✅ Done |
| 17.1 Local Embeddings | 2-3 дня | 17.0 |
| 17.2 Flask Integration | 4-5 дней | 17.1 (код + доки) |
| 17.3 API Reference | 2-3 дня | 17.1 |
| 17.4 Django | - | Future (не сейчас) |

**Итого:** ~10-12 дней работы

---

## 🚀 Workflow

### Приоритет выполнения

```
17.0 Audit (Done)
    ↓
17.1 Local Embeddings Docs ← Начать первым
    ↓
17.2 Flask Migration (код) ← СНАЧАЛА код
    ↓
17.2 Flask Docs (документация) ← ПОТОМ доки
    ↓
17.3 API Reference ← Параллельно с 17.2 docs
    ↓
17.4 Django (когда понадобится)
```

### Правила коммитов

Формат: `phase 17.N feat: <описание>`

Примеры:
- `phase 17.1 feat: Добавлена документация Qwen3-Embedding`
- `phase 17.2 feat: Flask App миграция на ComponentFactory`
- `phase 17.3 feat: Детальный API Reference для LocalEmbedder`

---

**Статус:** 🚧 In Progress | **Версия:** Draft | **Дата:** 11 декабря 2025
