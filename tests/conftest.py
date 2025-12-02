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
