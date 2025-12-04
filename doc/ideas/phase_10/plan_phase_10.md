# 🚀 Phase 10: Google Batch API Integration

**Цель:** Реализовать реальную интеграцию с Google Batch API для эмбеддингов, заменив текущую заглушку в `GeminiBatchClient`.

---

## 📊 Анализ текущей ситуации

### Что есть (Phase 5 legacy)

| Компонент | Статус | Описание |
|-----------|--------|----------|
| `BatchJobModel` | ✅ Готов | Таблица для хранения состояния batch-заданий |
| `ChunkModel.embedding_status` | ✅ Готов | Поля PENDING/READY/FAILED |
| `BatchManager` | ✅ Готов | Оркестратор очереди (flush_queue, sync_status) |
| `GeminiBatchClient` | ❌ Заглушка | `NotImplementedError` во всех методах |
| `PeeweeVectorStore.bulk_update_vectors()` | ✅ Готов | Массовое обновление векторов |
| `SemanticCore.ingest(mode='async')` | ✅ Готов | Сохранение чанков без векторов |

### Что нужно реализовать

**GeminiBatchClient — "последняя миля":**

1. `create_embedding_job()` — создание batch job в Google
2. `get_job_status()` — проверка статуса
3. `retrieve_results()` — получение результатов

---

## 🔍 Исследование Google Batch API (Context7)

### Ключевое открытие

В новом SDK `google-genai` **НЕТ** специального метода `batches.create_embeddings()` для эмбеддингов!

Вместо этого используется **общий** метод `batches.create()` с JSONL файлом, содержащим запросы к любому API endpoint (включая embeddings).

### Формат JSONL для embeddings

```jsonl
{"key": "chunk_123", "request": {"model": "models/text-embedding-004", "contents": [{"parts": [{"text": "Текст чанка"}]}], "config": {"task_type": "RETRIEVAL_DOCUMENT", "output_dimensionality": 768}}}
{"key": "chunk_456", "request": {"model": "models/text-embedding-004", "contents": [{"parts": [{"text": "Другой чанк"}]}], "config": {"task_type": "RETRIEVAL_DOCUMENT", "output_dimensionality": 768}}}
```

**Важно:**

- Используется `key` (не `custom_id`)
- Формат `request` совпадает с синхронным `embed_content()`
- Поле `config` вместо `embedding_config`

### API Flow

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="...")

# 1. Загрузка JSONL файла
file = client.files.upload(
    file='requests.jsonl',
    config=types.UploadFileConfig(display_name='batch_embeddings')
)

# 2. Создание batch job
job = client.batches.create(
    model="models/text-embedding-004",
    src=f"files/{file.name}",
)

# 3. Polling статуса
completed_states = {'JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED'}
while job.state not in completed_states:
    job = client.batches.get(name=job.name)
    time.sleep(30)

# 4. Получение результатов (inlined в job.responses)
for response in job.responses:
    chunk_id = response.key
    if not response.error:
        embedding = response.response.embedding.values  # list[float]
```

### Статусы batch job

| Google State | Наш маппинг |
|--------------|-------------|
| `JOB_STATE_QUEUED` | QUEUED |
| `JOB_STATE_RUNNING` | RUNNING |
| `JOB_STATE_SUCCEEDED` | SUCCEEDED |
| `JOB_STATE_FAILED` | FAILED |
| `JOB_STATE_CANCELLED` | CANCELLED |

---

## 🏗️ План реализации

### Step 1: Обновить `_create_jsonl_file()`

**Текущая реализация (НЕВЕРНАЯ):**

```python
request = {
    "custom_id": chunk.id,  # ❌ Неверный ключ
    "request": {
        "model": self.model_name,
        "content": {"parts": [{"text": text}]},  # ❌ content вместо contents
        "config": {
            "task_type": "RETRIEVAL_DOCUMENT",
            "output_dimensionality": self.dimension,
        }
    }
}
```

**Нужно (ПРАВИЛЬНАЯ):**

```python
request = {
    "key": chunk.id,  # ✅ Правильный ключ
    "request": {
        "model": self.model_name,
        "contents": [{"parts": [{"text": text}]}],  # ✅ contents массив
        "config": {
            "task_type": "RETRIEVAL_DOCUMENT",
            "output_dimensionality": self.dimension,
        }
    }
}
```

---

### Step 2: Реализовать `create_embedding_job()`

```python
def create_embedding_job(self, chunks, context_texts=None) -> str:
    """Создаёт батч-задание для генерации эмбеддингов."""
    if not chunks:
        raise ValueError("Список чанков не может быть пустым")
    
    # 1. Создаём JSONL файл
    jsonl_path = self._create_jsonl_file(chunks, context_texts)
    
    try:
        # 2. Инициализируем новый SDK клиент
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=self.api_key)
        
        # 3. Загружаем файл в Google Cloud
        uploaded = client.files.upload(
            file=jsonl_path,
            config=types.UploadFileConfig(
                display_name=f"batch_embeddings_{uuid4().hex[:8]}"
            )
        )
        
        logger.debug("JSONL file uploaded", file_name=uploaded.name)
        
        # 4. Создаём batch job
        job = client.batches.create(
            model=self.model_name,
            src=f"files/{uploaded.name}",
        )
        
        logger.info(
            "Batch job created",
            job_name=job.name,
            file_name=uploaded.name,
            chunk_count=len(chunks),
        )
        
        return job.name
        
    finally:
        # Удаляем локальный временный файл
        Path(jsonl_path).unlink(missing_ok=True)
```

---

### Step 3: Реализовать `get_job_status()`

```python
def get_job_status(self, google_job_id: str) -> str:
    """Получить статус батч-задания."""
    logger.debug("Checking batch job status", job_id=google_job_id)
    
    try:
        from google import genai
        client = genai.Client(api_key=self.api_key)
        
        job = client.batches.get(name=google_job_id)
        
        # Маппинг статусов Google -> наши
        status_map = {
            'JOB_STATE_QUEUED': 'QUEUED',
            'JOB_STATE_RUNNING': 'RUNNING',
            'JOB_STATE_SUCCEEDED': 'SUCCEEDED',
            'JOB_STATE_FAILED': 'FAILED',
            'JOB_STATE_CANCELLED': 'CANCELLED',
            'JOB_STATE_PAUSED': 'PAUSED',
        }
        
        mapped_status = status_map.get(job.state, job.state)
        
        logger.debug(
            "Batch job status retrieved",
            google_state=job.state,
            mapped_status=mapped_status,
        )
        
        return mapped_status
        
    except Exception as e:
        logger.error(
            "Failed to get batch job status",
            job_id=google_job_id,
            error_type=type(e).__name__,
        )
        raise RuntimeError(f"Ошибка при получении статуса: {e}")
```

---

### Step 4: Реализовать `retrieve_results()`

```python
def retrieve_results(self, google_job_id: str) -> Dict[str, bytes]:
    """Скачать результаты завершённого батч-задания."""
    logger.debug("Retrieving batch results", job_id=google_job_id)
    
    try:
        from google import genai
        import struct
        
        client = genai.Client(api_key=self.api_key)
        
        # Получаем задание
        job = client.batches.get(name=google_job_id)
        
        if job.state != 'JOB_STATE_SUCCEEDED':
            raise RuntimeError(
                f"Задание не завершено. Статус: {job.state}"
            )
        
        results = {}
        failed_count = 0
        
        # Результаты инлайнятся в job.responses
        for response in job.responses:
            chunk_id = response.key
            
            # Проверяем на ошибку
            if response.error:
                logger.warning(
                    "Chunk embedding failed",
                    chunk_id=chunk_id,
                    error=response.error.message,
                )
                failed_count += 1
                continue
            
            # Извлекаем embedding
            embedding_values = response.response.embedding.values
            
            # Конвертируем в bytes через struct.pack
            vector_blob = struct.pack(
                f"{len(embedding_values)}f",
                *embedding_values
            )
            results[chunk_id] = vector_blob
        
        logger.info(
            "Batch results retrieved",
            success_count=len(results),
            failed_count=failed_count,
        )
        
        # Cleanup: удаляем входной файл из Google Cloud
        if job.source:
            try:
                file_name = job.source.split('/')[-1]
                client.files.delete(name=f"files/{file_name}")
                logger.trace("Input file deleted", file=file_name)
            except Exception as e:
                logger.warning(
                    "Failed to delete input file",
                    error=str(e)[:100],
                )
        
        return results
        
    except Exception as e:
        logger.error(
            "Failed to retrieve batch results",
            job_id=google_job_id,
            error_type=type(e).__name__,
        )
        raise RuntimeError(f"Ошибка при скачивании результатов: {e}")
```

---

### Step 5: Удалить устаревший код

**Убрать методы:**

- `_parse_results_jsonl()` — результаты теперь в `job.responses`
- `_cleanup_files()` — интегрирован в `retrieve_results()`

---

## ⚠️ Риски и неопределённости

### 1. Структура ответа для embeddings

**Вопрос:** Точная структура `response.response` для embedding запросов.

**Предположение (на основе Context7):**

```python
response.response.embedding.values  # list[float]
response.response.embedding.statistics.token_count  # int
```

**Решение:** E2E тест с реальным API для проверки.

---

### 2. Миграция SDK

**Проблема:**

- Текущий код: `import google.generativeai as genai` (старый SDK)
- Новая документация: `from google import genai` (новый SDK)

**Решение:**

1. Проверить наличие `google-genai` в `requirements.txt`
2. `GeminiBatchClient` → использовать `from google import genai` (новый)
3. `GeminiEmbedder` → оставить `google.generativeai` (работает как есть)

**Проверка совместимости:**

```python
# Старый SDK (embedder.py)
import google.generativeai as genai
genai.configure(api_key="...")
result = genai.embed_content(...)

# Новый SDK (batching.py)
from google import genai
client = genai.Client(api_key="...")
job = client.batches.create(...)
```

---

### 3. Лимиты Google Batch API

| Лимит | Значение | Решение |
|-------|----------|---------|
| Max requests per batch | 10,000 | Добавить `max_size=10000` в `flush_queue()` |
| Max file size | 100 MB | Оценка: ~10KB на запрос = 10K запросов OK |
| Max concurrent jobs | 50 | Логирование warning при достижении |
| Timeout | 24 часа | Acceptable для batch режима |

---

### 4. Partial failures

**Сценарий:** 100 запросов, 5 провалены (токен-лимит, invalid text).

**Текущая логика в `BatchManager`:**

- Весь батч помечается `FAILED` → неправильно!

**Улучшение Phase 10:**

```python
# В retrieve_results()
for response in job.responses:
    if response.error:
        # Пропускаем, но логируем
        failed_chunks.append(chunk_id)
        continue
    results[chunk_id] = vector_blob

# В BatchManager.sync_status()
if len(results) > 0:
    # Обновляем успешные
    store.bulk_update_vectors(results)
    # Помечаем проваленные как FAILED с индивидуальными ошибками
    for chunk_id in failed_chunks:
        ChunkModel.update(
            embedding_status=FAILED,
            error_message=f"Batch processing error: {error}"
        ).where(id=chunk_id).execute()
```

---

## 📋 Чеклист реализации

### Phase 10.1: Инфраструктура ✅

- [ ] Обновить `_create_jsonl_file()`:
  - [ ] `key` вместо `custom_id`
  - [ ] `contents` массив вместо `content` объект
- [ ] Реализовать `create_embedding_job()`:
  - [ ] Инициализация `genai.Client`
  - [ ] Загрузка через `files.upload()`
  - [ ] Создание через `batches.create()`
- [ ] Реализовать `get_job_status()`:
  - [ ] Маппинг статусов
  - [ ] Error handling
- [ ] Реализовать `retrieve_results()`:
  - [ ] Парсинг `job.responses`
  - [ ] Конвертация в bytes
  - [ ] Cleanup файлов
- [ ] Удалить устаревшие методы:
  - [ ] `_parse_results_jsonl()`
  - [ ] `_cleanup_files()`

### Phase 10.2: Интеграция ✅

- [ ] Проверить совместимость с `BatchManager`:
  - [ ] `flush_queue()` вызывает правильный метод
  - [ ] `sync_status()` обрабатывает результаты
- [ ] Добавить `max_size=10000` в `flush_queue()`
- [ ] Улучшить обработку partial failures в `BatchManager`

### Phase 10.3: Тестирование ✅

- [ ] Unit-тесты:
  - [ ] `test_create_jsonl_format()` — проверка JSONL структуры
  - [ ] `test_status_mapping()` — маппинг статусов
  - [ ] `test_vector_conversion()` — bytes формат
- [ ] Integration-тесты:
  - [ ] Mock `genai.Client`
  - [ ] Mock `files.upload()`, `batches.create()`
  - [ ] Симуляция частичных ошибок
- [ ] E2E тест:
  - [ ] Реальный Batch API (2-3 чанка)
  - [ ] Проверка формата ответа
  - [ ] Измерение времени обработки

### Phase 10.4: Документация ✅

- [ ] Обновить `22_batch_manager.md`:
  - [ ] Добавить реальный API flow
  - [ ] Примеры JSONL формата
- [ ] Создать `49_batch_api_troubleshooting.md`:
  - [ ] Частые ошибки
  - [ ] Debugging tips
- [ ] README.md:
  - [ ] Пример async mode
  - [ ] Требования (API ключи)

---

## 🎯 Критерии успеха

1. ✅ **Функциональность:** `BatchManager.flush_queue()` создаёт реальный Google job
2. ✅ **Синхронизация:** `sync_status()` получает вектора и обновляет БД
3. ✅ **Экономия:** Подтверждённая 50% скидка в Google Cloud биллинге
4. ✅ **Надёжность:** Обработка partial failures без потери данных
5. ✅ **E2E:** Тест с реальным API проходит успешно

---

## 📚 Ссылки

- **Google GenAI Python SDK** — Context7 ID: `/googleapis/python-genai`
- **Batch API Docs** — <https://github.com/googleapis/python-genai/blob/main/README.md#batches>
- **Phase 5 Plan** — [../phase_5/plan_phase_5.md](../phase_5/plan_phase_5.md)
- **21_batch_api_economics.md** — [../../architecture/21_batch_api_economics.md](../../architecture/21_batch_api_economics.md)
- **22_batch_manager.md** — [../../architecture/22_batch_manager.md](../../architecture/22_batch_manager.md)

---

## 🚧 Потенциальные проблемы

### Problem 1: Новый SDK не установлен

**Симптом:**

```python
ModuleNotFoundError: No module named 'google.genai'
```

**Решение:**

```bash
pip install google-genai>=1.0.0
```

---

### Problem 2: Конфликт SDK версий

**Симптом:**

```python
AttributeError: 'module' object has no attribute 'batches'
```

**Решение:**

```python
# Проверить версию
import google.genai
print(google.genai.__version__)

# Должно быть >= 1.0.0
```

---

### Problem 3: Формат ответа отличается

**Симптом:**

```python
AttributeError: 'BatchJobResponse' object has no attribute 'embedding'
```

**Решение:**

- Запустить E2E тест с реальным API
- Вывести структуру `response.response` в лог
- Скорректировать парсинг в `retrieve_results()`

---

## 📝 Заметки для реализации

1. **SDK Migration:** Новый SDK (`google-genai`) — это **замена** старого (`google-generativeai`), но они могут сосуществовать.

2. **JSONL Format:** Критически важно использовать `contents` (массив), а не `content` (объект).

3. **Response Structure:** Результаты **инлайнятся** в `job.responses`, НЕ требуют отдельного скачивания JSONL файла.

4. **Cleanup:** Google хранит файлы **вечно**, если не удалить. Обязательно вызывать `files.delete()`.

5. **Error Handling:** Batch API может вернуть **частичный успех** — обрабатываем каждый response отдельно.
