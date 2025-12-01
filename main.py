"""
Playground для тестирования Parent-Child архитектуры семантического поиска.

Демонстрирует:
1. Инициализацию БД с поддержкой чанков
2. Загрузку реальных длинных документов из doc/architecture/
3. Автоматическую нарезку на чанки с перекрытием
4. Векторный поиск по чанкам с агрегацией по родителям
5. Полнотекстовый поиск по полным документам
6. Гибридный поиск с RRF
"""

from pathlib import Path

from semantic_core import (
    init_database,
    EmbeddingGenerator,
    SimpleTextSplitter,
    save_note_with_chunks,
    vector_search_chunks,
    fulltext_search_parents,
    hybrid_search_rrf,
)
from semantic_core.database import create_vector_table, create_fts_table
from domain.models import Note, NoteChunk, Category, Tag, NoteTag


def initialize_database():
    """Инициализирует БД и создает все таблицы для Parent-Child архитектуры."""
    print("🔧 Инициализация базы данных...")

    # Подключаемся к БД
    db = init_database()
    db.connect()

    # Создаем обычные таблицы
    db.create_tables([Category, Tag, Note, NoteChunk, NoteTag], safe=True)

    # Создаем виртуальные таблицы для поиска
    # Векторы теперь хранятся в NoteChunk, а не в Note!
    create_vector_table(NoteChunk, vector_column="embedding")
    # FTS остается на родительской таблице Note
    create_fts_table(Note, text_columns=["title", "content"])

    print("✅ База данных готова!")
    print("   → Note (parent) - для полнотекстового поиска")
    print("   → NoteChunk (child) - для векторного поиска\n")
    return db


def seed_data():
    """Заполняет БД реальными документами из doc/architecture/."""
    print("🌱 Загрузка документов из doc/architecture/...")

    # Создаем категорию
    cat_docs = Category.create(name="Документация")

    # Инициализируем инструменты
    generator = EmbeddingGenerator()
    splitter = SimpleTextSplitter(
        chunk_size=1000,  # ~250 токенов
        overlap=200,      # Перекрытие для контекста
        threshold=100     # Окно поиска переноса строки
    )

    # Загружаем все markdown файлы
    docs_dir = Path("doc/architecture")
    md_files = sorted(docs_dir.glob("*.md"))

    total_chunks = 0

    for md_file in md_files:
        # Читаем содержимое
        content = md_file.read_text(encoding="utf-8")
        title = md_file.stem.replace("_", " ").title()

        # Формируем данные заметки
        note_data = {
            "title": title,
            "content": content,
            "category": cat_docs,
        }

        # Сохраняем с автоматической нарезкой
        note = save_note_with_chunks(
            note_model=Note,
            chunk_model=NoteChunk,
            note_data=note_data,
            splitter=splitter,
            generator=generator,
        )

        chunks_count = note.chunks.count()
        total_chunks += chunks_count
        
        print(f"  ✓ {note.title[:40]:40} | {len(content):>6} символов | {chunks_count:>2} чанков")

    print(f"\n✅ Загружено {len(md_files)} документов, создано {total_chunks} чанков")
    print(f"   Средний размер документа: {sum(len(f.read_text()) for f in md_files) / len(md_files):.0f} символов")
    print(f"   Среднее количество чанков: {total_chunks / len(md_files):.1f}\n")


def test_vector_search():
    """Тест 1: Векторный поиск по чанкам с агрегацией."""
    print("🔍 Тест 1: Векторный поиск (по чанкам)")
    print("Запрос: 'Как работает векторный поиск?'\n")

    results = vector_search_chunks(
        parent_model=Note,
        chunk_model=NoteChunk,
        query="Как работает векторный поиск?",
        limit=3
    )

    print(f"Найдено: {len(results)} уникальных документов")
    for i, (note, distance) in enumerate(results, 1):
        chunks_count = note.chunks.count()
        print(f"  {i}. {note.title[:50]:50} | {chunks_count:>2} чанков | distance: {distance:.4f}")
    print()


def test_fulltext_search():
    """Тест 2: Полнотекстовый поиск по родителям."""
    print("🔎 Тест 2: Полнотекстовый поиск (по полным документам)")
    print("Запрос: 'Gemini API'\n")

    results = fulltext_search_parents(
        parent_model=Note,
        query="Gemini API",
        limit=3
    )

    print(f"Найдено: {len(results)} документов")
    for i, (note, rank) in enumerate(results, 1):
        print(f"  {i}. {note.title[:50]:50} | BM25: {rank:.4f}")
    print()


def test_chunk_details():
    """Тест 3: Просмотр чанков конкретного документа."""
    print("📄 Тест 3: Детали нарезки документа")
    
    # Берем первый документ
    note = Note.select().first()
    
    if not note:
        print("Нет документов для отображения\n")
        return
    
    print(f"Документ: {note.title}")
    print(f"Размер: {len(note.content)} символов")
    print(f"Чанков: {note.chunks.count()}\n")
    
    if note.chunks.count() > 0:
        print("Первые 3 чанка:")
        for chunk in note.chunks.order_by(NoteChunk.chunk_index).limit(3):
            preview = chunk.content[:80].replace("\n", " ")
            print(f"  [{chunk.chunk_index}] {preview}...")
    else:
        print("Чанков нет (данные не загружены)")
    print()


def test_hybrid_search():
    """Тест 4: Гибридный поиск с RRF."""
    print("⚡ Тест 4: Гибридный поиск (RRF: векторы + FTS)")
    print("Запрос: 'эмбеддинги модель'\n")

    results = hybrid_search_rrf(
        parent_model=Note,
        chunk_model=NoteChunk,
        query="эмбеддинги модель",
        limit=5
    )

    print(f"Найдено: {len(results)} документов (ранжировано по RRF)")
    for i, (note, rrf_score) in enumerate(results, 1):
        chunks_count = note.chunks.count()
        print(f"  {i}. {note.title[:45]:45} | {chunks_count:>2} чанков | RRF: {rrf_score:.4f}")
    print()


def main():
    """Основной сценарий тестирования Parent-Child архитектуры."""
    print("=" * 70)
    print("🚀 POC: Семантический поиск с Parent-Child архитектурой")
    print("   SQLite + Vec + Gemini + Chunking")
    print("=" * 70)
    print()

    # Инициализация
    db = initialize_database()

    # Загрузка реальных документов
    if Note.select().count() == 0 or NoteChunk.select().count() == 0:
        # Очищаем старые данные если есть
        if Note.select().count() > 0:
            print("⚠️  Обнаружены старые данные без чанков, очищаем...\n")
            NoteTag.delete().execute()
            NoteChunk.delete().execute()
            Note.delete().execute()
            Tag.delete().execute()
            Category.delete().execute()
        
        seed_data()
    else:
        notes_count = Note.select().count()
        chunks_count = NoteChunk.select().count()
        print(f"ℹ️  База содержит {notes_count} документов и {chunks_count} чанков\n")

    # Запускаем тесты
    test_vector_search()
    test_fulltext_search()
    test_chunk_details()
    test_hybrid_search()

    # Статистика
    print("=" * 70)
    print("📊 Статистика:")
    total_notes = Note.select().count()
    total_chunks = NoteChunk.select().count()
    avg_chunks = total_chunks / total_notes if total_notes > 0 else 0
    
    print(f"   Документов: {total_notes}")
    print(f"   Чанков: {total_chunks}")
    print(f"   Среднее чанков/документ: {avg_chunks:.1f}")
    print("=" * 70)
    print("✅ Все тесты выполнены!")
    print("=" * 70)

    # Закрываем соединение
    db.close()


if __name__ == "__main__":
    main()
