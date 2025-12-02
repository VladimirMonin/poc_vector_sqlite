"""
Конфигурация pytest для тестов POC.

Определяет фикстуры для:
- Инициализации тестовой базы данных (новая и старая архитектура)
- Создания тестовых данных
- Очистки после тестов
"""

import pytest
import tempfile
from pathlib import Path

# Новая архитектура (Фаза 1)
from semantic_core import (
    init_peewee_database,
    PeeweeVectorStore,
    GeminiEmbedder,
    SimpleSplitter,
    BasicContextStrategy,
    SemanticCore,
)

# Старая архитектура (для обратной совместимости старых тестов)
try:
    from semantic_core.database import (
        init_database,
        create_vector_table,
        create_fts_table,
        db,
    )
    from semantic_core.embeddings import EmbeddingGenerator
    from semantic_core.text_processing import SimpleTextSplitter
    from domain.models import Note, NoteChunk, Category, Tag, NoteTag

    OLD_API_AVAILABLE = True
except ImportError:
    OLD_API_AVAILABLE = False


@pytest.fixture(scope="session")
def temp_db_path():
    """
    Создает временный файл базы данных для тестов.

    Scope: session - один файл на весь сеанс тестов.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    yield db_path

    # Cleanup: удаляем временный файл после всех тестов
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(scope="function")
def test_db(temp_db_path):
    """
    Инициализирует тестовую базу данных (старый API).

    Scope: function - каждый тест получает чистую базу.
    """
    if not OLD_API_AVAILABLE:
        pytest.skip("Старый API недоступен")

    # Инициализируем БД
    database = init_database(temp_db_path)
    database.connect()

    # Создаем таблицы
    database.create_tables([Category, Tag, Note, NoteChunk, NoteTag])

    # Создаем виртуальные таблицы
    create_vector_table(NoteChunk, vector_column="embedding")
    create_fts_table(Note, text_columns=["title", "content"])

    yield database

    # Cleanup: удаляем все таблицы после теста
    # Сначала удаляем виртуальные таблицы
    try:
        database.execute_sql("DROP TABLE IF EXISTS note_chunks_vec")
        database.execute_sql("DROP TABLE IF EXISTS notes_fts")
    except Exception:
        pass  # Игнорируем ошибки при удалении виртуальных таблиц

    database.drop_tables([NoteTag, NoteChunk, Note, Tag, Category], safe=True)
    database.close()


@pytest.fixture
def sample_category(test_db):
    """Создает тестовую категорию."""
    if not OLD_API_AVAILABLE:
        pytest.skip("Старый API недоступен")
    category = Category.create(name="Python")
    return category


@pytest.fixture
def sample_tags(test_db):
    """Создает набор тестовых тегов."""
    if not OLD_API_AVAILABLE:
        pytest.skip("Старый API недоступен")
    tags = [
        Tag.create(name="#код"),
        Tag.create(name="#обучение"),
        Tag.create(name="#важно"),
    ]
    return tags


@pytest.fixture
def embedding_generator():
    """Создает экземпляр генератора эмбеддингов (старый API)."""
    if not OLD_API_AVAILABLE:
        pytest.skip("Старый API недоступен")
    return EmbeddingGenerator()


@pytest.fixture
def text_splitter():
    """Создает экземпляр сплиттера с тестовыми параметрами (старый API)."""
    if not OLD_API_AVAILABLE:
        pytest.skip("Старый API недоступен")
    return SimpleTextSplitter(
        chunk_size=500,  # Меньше для быстрых тестов
        overlap=100,
        threshold=50,
    )


@pytest.fixture
def long_text():
    """
    Возвращает длинный текст для тестирования чанкинга.

    Примерно 2000 символов - достаточно для 4-5 чанков.
    """
    return """
Python — это высокоуровневый язык программирования общего назначения.

Он отличается простым и понятным синтаксисом, что делает его идеальным 
для начинающих программистов. В то же время Python достаточно мощный 
для создания сложных приложений.

Основные особенности Python:
- Динамическая типизация
- Автоматическое управление памятью
- Объектно-ориентированное программирование
- Функциональное программирование
- Огромная стандартная библиотека

Python активно используется в различных областях:
1. Веб-разработка (Django, Flask, FastAPI)
2. Data Science и машинное обучение (NumPy, Pandas, scikit-learn)
3. Автоматизация и скриптинг
4. Научные вычисления
5. Разработка игр

Циклы в Python бывают двух типов: for и while.

Цикл for используется для итерации по последовательности:
```python
for i in range(10):
    print(i)
```

Цикл while выполняется, пока условие истинно:
```python
counter = 0
while counter < 10:
    print(counter)
    counter += 1
```

Также в Python есть генераторы списков (list comprehensions):
```python
squares = [x**2 for x in range(10)]
```

Это очень мощный инструмент для создания списков на основе других последовательностей.

Обработка исключений в Python выполняется с помощью конструкции try-except:
```python
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Деление на ноль!")
```

Python поддерживает множественное наследование и миксины, что позволяет 
создавать гибкие и переиспользуемые компоненты.

Виртуальные окружения (venv) позволяют изолировать зависимости проектов:
```bash
python -m venv myenv
source myenv/bin/activate  # Linux/Mac
myenv\\Scripts\\activate  # Windows
```

Менеджеры пакетов pip и poetry упрощают управление зависимостями.
    """.strip()


# ============================================================================
# Новые фикстуры для Phase 3 (Integration Layer)
# ============================================================================


@pytest.fixture
def mock_embedder():
    """Фейковый embedder для быстрых тестов без API вызовов.

    Возвращает детерминированные векторы на основе хеша текста.
    """
    from semantic_core.interfaces import BaseEmbedder

    class MockEmbedder(BaseEmbedder):
        def __init__(self, dim: int = 768):
            self.dim = dim

        def embed_query(self, text: str) -> list[float]:
            # Детерминированный вектор на основе хеша
            import hashlib
            import numpy as np

            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            # Генерируем псевдослучайный вектор
            vector = []
            for i in range(self.dim):
                vector.append(((hash_val + i) % 1000) / 1000.0 - 0.5)
            return np.array(vector, dtype=np.float32)

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [self.embed_query(text) for text in texts]

    return MockEmbedder()


@pytest.fixture
def in_memory_db():
    """In-memory SQLite база с sqlite-vec для тестов.

    Создает чистую БД для каждого теста.
    """
    db = init_peewee_database(":memory:")
    yield db
    db.close()


@pytest.fixture
def semantic_core(mock_embedder, in_memory_db):
    """Полностью настроенный SemanticCore для тестов.

    Использует mock embedder и in-memory DB.
    """
    store = PeeweeVectorStore(in_memory_db)
    splitter = SimpleSplitter(chunk_size=500, overlap=100)
    context_strategy = BasicContextStrategy()

    core = SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=splitter,
        context_strategy=context_strategy,
    )

    return core


@pytest.fixture
def create_test_model(in_memory_db, semantic_core):
    """Фабрика для создания тестовых Peewee моделей с SemanticIndex.

    Использование:
        >>> TestModel = create_test_model(
        ...     fields={'title': CharField(), 'body': TextField()},
        ...     index_config={'content_field': 'body', 'context_fields': ['title']}
        ... )
    """
    from peewee import Model, CharField, TextField
    from semantic_core import SemanticIndex

    created_models = []

    def factory(fields: dict, index_config: dict, model_name: str = "TestModel"):
        """Создает динамическую модель Peewee с SemanticIndex.

        Args:
            fields: Словарь {имя_поля: Field()}.
            index_config: Конфигурация для SemanticIndex.
            model_name: Имя класса модели.

        Returns:
            Класс модели с дескриптором SemanticIndex.
        """
        # Создаем класс модели динамически
        class_dict = {"__module__": __name__}
        class_dict.update(fields)

        # Добавляем Meta
        class Meta:
            database = in_memory_db

        class_dict["Meta"] = Meta

        # Добавляем SemanticIndex
        class_dict["search"] = SemanticIndex(core=semantic_core, **index_config)

        # Создаем класс
        TestModel = type(model_name, (Model,), class_dict)

        # ВАЖНО: При создании класса через type() дескрипторный протокол
        # __set_name__ не вызывается автоматически. Вызываем вручную.
        if hasattr(TestModel.search, "__set_name__"):
            TestModel.search.__set_name__(TestModel, "search")

        # Создаем таблицы
        in_memory_db.create_tables([TestModel])

        created_models.append(TestModel)

        return TestModel

    yield factory

    # Cleanup: удаляем все созданные таблицы
    if created_models:
        in_memory_db.drop_tables(created_models, safe=True)


# ============================================================================
# Фикстуры для Phase 4 (Smart Parsing & Granular Search)
# ============================================================================


@pytest.fixture
def fixtures_dir():
    """Путь к директории с test fixtures."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def real_docs_dir(fixtures_dir):
    """Путь к директории с реальными документами для тестирования."""
    return fixtures_dir / "real_docs"


@pytest.fixture
def evil_md_path(real_docs_dir):
    """Путь к evil.md с edge cases."""
    return real_docs_dir / "evil.md"


@pytest.fixture
def evil_md_content(evil_md_path):
    """Содержимое evil.md."""
    return evil_md_path.read_text(encoding="utf-8")


@pytest.fixture
def markdown_parser():
    """Экземпляр MarkdownNodeParser для тестов."""
    from semantic_core.processing.parsers.markdown_parser import MarkdownNodeParser

    return MarkdownNodeParser()


@pytest.fixture
def smart_splitter(markdown_parser):
    """Экземпляр SmartSplitter с MarkdownNodeParser."""
    from semantic_core.processing.splitters.smart_splitter import SmartSplitter

    return SmartSplitter(
        parser=markdown_parser,
        chunk_size=1000,
        code_chunk_size=2000,
        preserve_code=True,
    )


@pytest.fixture
def hierarchical_context():
    """Экземпляр HierarchicalContextStrategy для тестов."""
    from semantic_core.processing.context.hierarchical_strategy import (
        HierarchicalContextStrategy,
    )

    return HierarchicalContextStrategy(include_doc_title=True)


@pytest.fixture
def smart_semantic_core(
    mock_embedder, in_memory_db, smart_splitter, hierarchical_context
):
    """SemanticCore с умным парсингом для Phase 4 тестов."""
    from semantic_core import PeeweeVectorStore, SemanticCore

    store = PeeweeVectorStore(in_memory_db)

    core = SemanticCore(
        embedder=mock_embedder,
        store=store,
        splitter=smart_splitter,
        context_strategy=hierarchical_context,
    )

    return core


# ============================================================================
# Фикстуры для Phase 5 (Async Batching)
# ============================================================================


@pytest.fixture
def google_keyring():
    """Тестовая конфигурация GoogleKeyring с моками ключей."""
    from semantic_core.domain import GoogleKeyring

    return GoogleKeyring(
        default_key="MOCK_DEFAULT_KEY",
        batch_key="MOCK_BATCH_KEY",
    )


@pytest.fixture
def google_keyring_no_batch():
    """GoogleKeyring без batch_key для тестирования валидации."""
    from semantic_core.domain import GoogleKeyring

    return GoogleKeyring(
        default_key="MOCK_DEFAULT_KEY",
        batch_key=None,
    )


@pytest.fixture
def mock_batch_client(mock_embedder):
    """Mock клиент для Google Batch API (без реальных вызовов).

    Эмулирует поведение GeminiBatchClient:
    - create_embedding_job -> возвращает mock job_id
    - get_job_status -> возвращает SUCCEEDED
    - retrieve_results -> возвращает фейковые векторы
    """
    import struct

    class MockBatchClient:
        def __init__(self):
            self.jobs = {}  # {job_id: {"status": str, "chunks": list}}
            self._job_counter = 0

        def create_embedding_job(self, chunks, context_texts=None):
            """Создаёт фейковое задание."""
            job_id = f"mock-batch-job-{self._job_counter}"
            self._job_counter += 1

            self.jobs[job_id] = {
                "status": "RUNNING",
                "chunks": chunks,
                "context_texts": context_texts or {},
            }

            return job_id

        def get_job_status(self, job_id):
            """Возвращает статус (по умолчанию SUCCEEDED)."""
            if job_id not in self.jobs:
                return "FAILED"
            return self.jobs[job_id]["status"]

        def set_job_status(self, job_id, status):
            """Вспомогательный метод для тестов - установить статус."""
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = status

        def retrieve_results(self, job_id):
            """Возвращает фейковые векторы для чанков."""
            if job_id not in self.jobs:
                raise RuntimeError(f"Job {job_id} not found")

            job = self.jobs[job_id]
            if job["status"] != "SUCCEEDED":
                raise RuntimeError(f"Job not completed: {job['status']}")

            # Генерируем фейковые векторы через mock_embedder
            results = {}
            for chunk in job["chunks"]:
                # Используем context_text если есть, иначе content
                text = job["context_texts"].get(chunk.id, chunk.content)
                vector = mock_embedder.embed_query(text)

                # Конвертируем в bytes
                blob = struct.pack(f"{len(vector)}f", *vector.tolist())
                results[chunk.id] = blob

            return results

    return MockBatchClient()


@pytest.fixture
def batch_manager(google_keyring, in_memory_db, mock_batch_client):
    """BatchManager с mock клиентом для тестов."""
    from semantic_core import BatchManager, PeeweeVectorStore

    store = PeeweeVectorStore(in_memory_db)

    # Создаём менеджер и подменяем batch_client на мок
    manager = BatchManager(
        keyring=google_keyring,
        vector_store=store,
    )

    # Подмена реального клиента на мок
    manager.batch_client = mock_batch_client

    return manager


def pytest_configure(config):
    """Регистрация custom markers."""
    config.addinivalue_line(
        "markers", "real_api: Tests that make real API calls (expensive, slow)"
    )
