# 🔬 Inspector Core: ProviderInspector и SnapshotManager

> Provider-agnostic инспекция через duck typing

**Коммит:** `591f972` — phase 16.0 feat: Реализован Debug Observatory (Inspector Core)

---

## 🎯 Задача

Создать систему инспекции pipeline которая:

- ✅ Работает с **любыми** провайдерами (Gemini, MLX, OpenAI)
- ✅ **Не требует** изменения кода провайдеров
- ✅ Извлекает метаданные через **duck typing**
- ✅ Сохраняет **полные снимки** выполнения
- ✅ Поддерживает **сравнение** конфигураций

---

## 🏗️ Архитектура

```
┌────────────────────────────────────────────────────────────────┐
│                    ProviderInspector                           │
│                                                                │
│  Задачи:                                                       │
│  1. Перехват вызовов SemanticCore                            │
│  2. Извлечение метаданных провайдеров (duck typing)          │
│  3. Захват промежуточных состояний                           │
│  4. Создание InspectionSnapshot                               │
└──────────────────┬─────────────────────────────────────────────┘
                   │
                   │ uses
                   ▼
┌────────────────────────────────────────────────────────────────┐
│                  SnapshotManager                               │
│                                                                │
│  Задачи:                                                       │
│  1. Создание сессионных папок                                 │
│  2. Сохранение snapshot в JSON                                │
│  3. Загрузка snapshot из JSON                                 │
│  4. Поддержка gzip compression                                │
└──────────────────┬─────────────────────────────────────────────┘
                   │
                   │ produces
                   ▼
┌────────────────────────────────────────────────────────────────┐
│                InspectionSnapshot                              │
│                                                                │
│  Содержит:                                                     │
│  - file_path, file_content (входные данные)                   │
│  - embedder/transcriber/vision metadata (провайдеры)          │
│  - chunks (все чанки с embeddings)                            │
│  - searches (результаты поиска)                               │
│  - steps (пошаговые логи)                                     │
│  - total_duration_ms                                          │
└────────────────────────────────────────────────────────────────┘
```

---

## 📦 ProviderInspector

### Основная идея

**Provider-agnostic** = работает с любыми провайдерами БЕЗ изменения их кода.

**Как?** Через **duck typing** — извлекаем атрибуты провайдеров динамически:

```python
class ProviderInspector:
    """Provider-agnostic inspector."""
    
    def __init__(
        self, 
        core: SemanticCore,
        artifacts_root: Optional[Path] = None
    ):
        self.core = core
        if artifacts_root:
            self.snapshot_manager = SnapshotManager(artifacts_root=Path(artifacts_root))
        else:
            self.snapshot_manager = SnapshotManager()
```

**Ключевой момент:** Принимаем `SemanticCore`, а не конкретные провайдеры!

### Извлечение метаданных (Duck Typing)

```python
def _extract_provider_metadata(self, provider) -> Optional[ProviderMetadata]:
    """Извлекает метаданные из провайдера через duck typing.
    
    Graceful degradation: если атрибут отсутствует → None.
    """
    if provider is None:
        return None
    
    provider_type = type(provider).__name__
    
    # Duck typing: пытаемся извлечь атрибуты
    model_name = getattr(provider, "model", None)
    dimension = getattr(provider, "dimension", None)
    max_tokens = getattr(provider, "max_tokens", None)
    device = getattr(provider, "device", None)
    
    # Extra info (например, has_api_key для облачных провайдеров)
    extra = {}
    if hasattr(provider, "api_key"):
        extra["has_api_key"] = bool(provider.api_key)
    
    return ProviderMetadata(
        provider_type=provider_type,
        model_name=model_name,
        dimension=dimension,
        max_tokens=max_tokens,
        device=device,
        extra=extra
    )
```

**Преимущества duck typing:**

✅ **Работает с любыми провайдерами:**

```python
# GeminiEmbedder
embedder_meta = inspector._extract_provider_metadata(gemini_embedder)
# ProviderMetadata(provider_type='GeminiEmbedder', model_name=None, dimension=768)

# MLXEmbedder (гипотетический)
embedder_meta = inspector._extract_provider_metadata(mlx_embedder)
# ProviderMetadata(provider_type='MLXEmbedder', model_name='all-MiniLM', device='mps')
```

✅ **Graceful degradation:**

```python
# Если провайдер не имеет атрибута model → model_name=None
# Но inspector всё равно работает!
```

✅ **Не требует изменения провайдеров:**

```python
# Не нужно добавлять методы get_metadata() в каждый провайдер
# Просто извлекаем публичные атрибуты
```

### Инспекция Ingest

```python
def ingest_with_inspection(self, path: str) -> InspectionSnapshot:
    """Выполняет ingest с полной инспекцией.
    
    Шаги:
    1. Извлекаем метаданные провайдеров
    2. Читаем входной файл
    3. Запускаем core.ingest()
    4. Собираем чанки из БД
    5. Создаём snapshot
    """
    start_time = time.time()
    steps = []
    
    # Шаг 1: Метаданные провайдеров
    embedder_meta = self._extract_provider_metadata(self.core.embedder)
    transcriber_meta = self._extract_provider_metadata(self.core.transcriber)
    vision_meta = self._extract_provider_metadata(self.core.vision_analyzer)
    
    logger.info("metadata_extracted", 
                embedder=embedder_meta.provider_type if embedder_meta else None)
    
    # Шаг 2: Читаем входной файл
    file_path = Path(path)
    file_content = file_path.read_text(encoding="utf-8")
    
    # Шаг 3: Запускаем pipeline
    step_start = time.time()
    document = self.core.ingest(path)
    steps.append({
        "step_name": "ingest",
        "duration_ms": (time.time() - step_start) * 1000
    })
    
    # Шаг 4: Собираем чанки из БД
    chunks_inspection = []
    
    # Получаем чанки через store
    chunk_models = self.core.store.db.execute_sql(
        "SELECT id, content, embedding FROM chunks WHERE document_id = ?",
        (document.id,)
    ).fetchall()
    
    for chunk_id, content, embedding_blob in chunk_models:
        # Десериализуем embedding
        embedding = np.frombuffer(embedding_blob, dtype=np.float32)
        
        chunks_inspection.append(ChunkInspection(
            chunk_id=chunk_id,
            content=content,
            embedding_preview=embedding[:20].tolist(),  # Первые 20 значений
            embedding_dimension=len(embedding),
            embedding_hash=hashlib.md5(embedding_blob).hexdigest()[:8]
        ))
    
    # Шаг 5: Создаём snapshot
    total_duration = (time.time() - start_time) * 1000
    
    snapshot = InspectionSnapshot(
        file_path=str(file_path),
        file_content=file_content,  # ← Важно! Сохраняем копию
        processing_timestamp=datetime.now().isoformat(),
        embedder_metadata=embedder_meta,
        transcriber_metadata=transcriber_meta,
        vision_metadata=vision_meta,
        chunks=chunks_inspection,
        searches=[],
        steps=steps,
        total_duration_ms=total_duration
    )
    
    logger.info("inspection_completed", chunks=len(chunks_inspection))
    
    return snapshot
```

**Ключевые детали:**

**1. Копия входного файла:**

```python
file_content = file_path.read_text(encoding="utf-8")
# Сохраняем в snapshot.file_content
```

**Зачем?** Чтобы snapshot был **самодостаточным**:

- Можно воспроизвести инспекцию позже
- Можно сравнивать конфигурации на одном контенте
- Golden-file тесты работают даже если файл изменился

**2. Embedding preview:**

```python
embedding_preview=embedding[:20].tolist()  # Первые 20 значений
```

**Зачем?** Полный embedding 768D занимает много места в JSON. Preview достаточно для:

- Проверки что embedding создан
- Быстрого сравнения (первые 20 значений отличаются → весь вектор отличается)

**3. Embedding hash:**

```python
embedding_hash=hashlib.md5(embedding_blob).hexdigest()[:8]
```

**Зачем?** Для быстрого сравнения embeddings между снимками:

- Одинаковый hash → embeddings идентичны
- Разный hash → провайдеры дали разные результаты

### Инспекция Search

```python
def search_with_inspection(
    self,
    query: str,
    top_k: int = 5,
    mode: str = "hybrid"
) -> InspectionSnapshot:
    """Выполняет поиск с инспекцией."""
    start_time = time.time()
    
    # Запускаем поиск
    results = self.core.search(query, mode=mode, limit=top_k)
    
    # Собираем результаты
    search_results = []
    for result in results:
        search_results.append({
            "chunk_id": result.chunk_id,
            "content": result.document.content[:200],  # Preview
            "similarity": result.score,
            "match_type": result.match_type.value
        })
    
    search_inspection = SearchInspection(
        query=query,
        search_mode=mode,
        limit=top_k,
        results_count=len(results),
        results=search_results
    )
    
    # Создаём snapshot с поиском
    snapshot = InspectionSnapshot(
        file_path="",  # Для search нет входного файла
        file_content="",
        processing_timestamp=datetime.now().isoformat(),
        embedder_metadata=self._extract_provider_metadata(self.core.embedder),
        chunks=[],
        searches=[search_inspection],
        steps=[{
            "step_name": "search",
            "duration_ms": (time.time() - start_time) * 1000
        }],
        total_duration_ms=(time.time() - start_time) * 1000
    )
    
    logger.info("search_completed", results=len(results))
    
    return snapshot
```

---

## 📦 SnapshotManager

### Задачи

1. **Создание структурированных папок** для артефактов
2. **Сохранение snapshot** в JSON (с опциональным сжатием)
3. **Загрузка snapshot** из JSON
4. **Serialization** dataclass → dict → JSON

### Структура артефактов

```
tests/e2e/audit/snapshots/
└── session_2025-12-10_14-30-15/
    ├── example_md_inspection.json      # Полный snapshot
    ├── input_example.md                # Копия входного файла (CLI)
    ├── similarities.csv                # Similarity matrix (CLI)
    └── report.md                       # Markdown отчёт (CLI)
```

**Соглашения:**

- `session_YYYY-MM-DD_HH-MM-SS/` — уникальная папка для каждой инспекции
- `{file_prefix}_inspection.json` — основной snapshot
- Дополнительные артефакты создаются CLI/reporters

### Создание сессии

```python
def create_session_folder(
    self, 
    session_name: Optional[str] = None
) -> Path:
    """Создаёт папку для сессии.
    
    Args:
        session_name: Имя сессии или None (авто timestamp)
    
    Returns:
        Path к созданной папке
    """
    if session_name is None:
        session_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    session_path = self.artifacts_root / session_name
    session_path.mkdir(parents=True, exist_ok=True)
    
    logger.debug("session_folder_created", session_path=str(session_path))
    
    return session_path
```

**Пример:**

```python
manager = SnapshotManager(artifacts_root=Path("./snapshots"))

session = manager.create_session_folder()
# Path("./snapshots/2025-12-10_14-30-15")

custom_session = manager.create_session_folder("my_test")
# Path("./snapshots/my_test")
```

### Сохранение snapshot

```python
def save_snapshot(
    self,
    snapshot: InspectionSnapshot,
    session_path: Path,
    file_prefix: str,
    compress: bool = False,
) -> Path:
    """Сохраняет snapshot в JSON.
    
    Args:
        snapshot: Снимок для сохранения
        session_path: Путь к папке сессии
        file_prefix: Префикс имени файла (example_md)
        compress: Сжимать ли gzip
    
    Returns:
        Path к сохранённому файлу
    """
    # Конвертируем dataclass → dict
    data = self._snapshot_to_dict(snapshot)
    
    # Определяем имя файла
    suffix = ".json.gz" if compress else ".json"
    filename = f"{file_prefix}_inspection{suffix}"
    filepath = session_path / filename
    
    # Сохраняем
    if compress:
        with gzip.open(filepath, "wt", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    else:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
    file_size = filepath.stat().st_size
    logger.info("snapshot_saved", 
                path=str(filepath), 
                size_bytes=file_size,
                compressed=compress)
    
    return filepath
```

**Ключевые детали:**

**1. Serialization через dataclasses.asdict():**

```python
def _snapshot_to_dict(self, snapshot: InspectionSnapshot) -> dict:
    """Конвертирует dataclass в dict для JSON."""
    data = {
        "file_path": snapshot.file_path,
        "file_content": snapshot.file_content,
        "processing_timestamp": snapshot.processing_timestamp,
        # ... остальные поля
    }
    
    # Конвертируем вложенные dataclass'ы
    if snapshot.embedder_metadata:
        data["embedder_metadata"] = {
            "provider_type": snapshot.embedder_metadata.provider_type,
            "model_name": snapshot.embedder_metadata.model_name,
            # ...
        }
    
    return data
```

**2. Опциональное сжатие:**

```python
# Без сжатия: example_md_inspection.json (150KB)
save_snapshot(snapshot, session_path, "example_md", compress=False)

# С сжатием: example_md_inspection.json.gz (40KB)
save_snapshot(snapshot, session_path, "example_md", compress=True)
```

**Когда использовать сжатие?**

- ✅ Большие snapshots (много чанков, длинный file_content)
- ✅ Долгосрочное хранение (экономия места)
- ❌ Частый доступ (распаковка медленнее)

### Загрузка snapshot

```python
def load_snapshot(self, path: Path) -> InspectionSnapshot:
    """Загружает snapshot из JSON.
    
    Args:
        path: Путь к файлу snapshot
    
    Returns:
        Восстановленный InspectionSnapshot
    """
    # Автоопределение сжатия по расширению
    is_compressed = path.suffix == ".gz"
    
    # Загружаем JSON
    if is_compressed:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    
    # Конвертируем dict → dataclass
    snapshot = self._dict_to_snapshot(data)
    
    logger.info("snapshot_loaded", path=str(path))
    
    return snapshot

def _dict_to_snapshot(self, data: dict) -> InspectionSnapshot:
    """Конвертирует dict в InspectionSnapshot."""
    
    # Восстанавливаем вложенные dataclass'ы
    embedder_meta = None
    if data.get("embedder_metadata"):
        embedder_meta = ProviderMetadata(**data["embedder_metadata"])
    
    chunks = []
    for chunk_data in data.get("chunks", []):
        chunks.append(ChunkInspection(**chunk_data))
    
    # ... аналогично для searches и т.д.
    
    return InspectionSnapshot(
        file_path=data["file_path"],
        file_content=data["file_content"],
        processing_timestamp=data["processing_timestamp"],
        embedder_metadata=embedder_meta,
        chunks=chunks,
        # ...
    )
```

---

## 📊 Модели данных

### ProviderMetadata

```python
@dataclass
class ProviderMetadata:
    """Метаданные провайдера."""
    
    provider_type: str              # "GeminiEmbedder", "MLXEmbedder"
    model_name: Optional[str]       # "text-embedding-004", None
    dimension: Optional[int]        # 768
    max_tokens: Optional[int]       # 2048
    device: Optional[str]           # "mps", "cuda", None
    extra: dict = field(default_factory=dict)  # Дополнительная info
```

**Пример:**

```python
ProviderMetadata(
    provider_type="GeminiEmbedder",
    model_name=None,  # GeminiEmbedder не сохраняет model
    dimension=768,
    max_tokens=2048,
    device=None,
    extra={"has_api_key": True}
)
```

### ChunkInspection

```python
@dataclass
class ChunkInspection:
    """Инспекция одного чанка."""
    
    chunk_id: int
    content: str                    # Полный текст чанка
    embedding_preview: List[float]  # Первые 20 значений
    embedding_dimension: int        # 768
    embedding_hash: str             # "a3f2c1d4" (MD5[:8])
```

**Пример:**

```python
ChunkInspection(
    chunk_id=1,
    content="# Introduction to Python\n\nPython is...",
    embedding_preview=[0.123, -0.456, 0.789, ...],  # 20 значений
    embedding_dimension=768,
    embedding_hash="a3f2c1d4"
)
```

### SearchInspection

```python
@dataclass
class SearchInspection:
    """Результаты поиска."""
    
    query: str
    search_mode: str                # "vector", "fts", "hybrid"
    limit: int
    results_count: int
    results: List[Dict[str, Any]]   # Список результатов
```

**Пример:**

```python
SearchInspection(
    query="What is Python?",
    search_mode="hybrid",
    limit=3,
    results_count=3,
    results=[
        {"chunk_id": 1, "similarity": 0.89, "content": "Python is..."},
        {"chunk_id": 2, "similarity": 0.76, "content": "Introduction..."},
        {"chunk_id": 3, "similarity": 0.65, "content": "Python programming..."}
    ]
)
```

### InspectionSnapshot

```python
@dataclass
class InspectionSnapshot:
    """Полный снимок инспекции."""
    
    # Входные данные
    file_path: str
    file_content: str
    processing_timestamp: str
    
    # Метаданные провайдеров
    embedder_metadata: Optional[ProviderMetadata]
    transcriber_metadata: Optional[ProviderMetadata]
    vision_metadata: Optional[ProviderMetadata]
    
    # Результаты обработки
    chunks: List[ChunkInspection]
    searches: List[SearchInspection]
    
    # Метрики
    steps: List[Dict[str, Any]]
    total_duration_ms: float
```

---

## 🎯 Использование

### Базовая инспекция

```python
from semantic_core.core.observatory import ProviderInspector
from semantic_core import create_core

# Создаём SemanticCore
core = create_core()

# Создаём Inspector
inspector = ProviderInspector(core=core)

# Инспекция ingest
snapshot = inspector.ingest_with_inspection("docs/example.md")

print(f"Chunks: {len(snapshot.chunks)}")
print(f"Provider: {snapshot.embedder_metadata.provider_type}")
print(f"Duration: {snapshot.total_duration_ms:.2f}ms")
```

### С сохранением артефактов

```python
from pathlib import Path

# Inspector с кастомной папкой
inspector = ProviderInspector(
    core=core,
    artifacts_root=Path("./my_snapshots")
)

# Инспекция
snapshot = inspector.ingest_with_inspection("docs/example.md")

# Сохранение
session = inspector.snapshot_manager.create_session_folder("test_run")
snapshot_path = inspector.snapshot_manager.save_snapshot(
    snapshot,
    session_path=session,
    file_prefix="example_md"
)

print(f"Snapshot saved: {snapshot_path}")
```

### Загрузка и сравнение

```python
# Загружаем старый snapshot
old_snapshot = inspector.snapshot_manager.load_snapshot(
    Path("./snapshots/2025-12-09_10-30-00/example_md_inspection.json")
)

# Делаем новый snapshot
new_snapshot = inspector.ingest_with_inspection("docs/example.md")

# Сравниваем
print(f"Old chunks: {len(old_snapshot.chunks)}")
print(f"New chunks: {len(new_snapshot.chunks)}")

# Сравниваем embeddings по hash
for old_c, new_c in zip(old_snapshot.chunks, new_snapshot.chunks):
    if old_c.embedding_hash != new_c.embedding_hash:
        print(f"Chunk {old_c.chunk_id}: embeddings changed!")
```

---

## 🔗 Связанные материалы

- [README.md](README.md) — обзор Phase 16
- [03_reporters.md](03_reporters.md) — экспорт snapshot в разные форматы
- [04_cli_inspect.md](04_cli_inspect.md) — CLI команда `semantic inspect`

---

**← [Назад к Phase 16](README.md)**
