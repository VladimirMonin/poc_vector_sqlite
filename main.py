"""
Playground для тестирования semantic_core.

Демонстрирует:
1. Инициализацию БД и создание таблиц
2. Seed данных (категории, теги, заметки)
3. Векторный поиск
4. Полнотекстовый поиск
5. Гибридный поиск с RRF
6. Фасетный поиск (с фильтрами)
"""

from semantic_core import init_database, EmbeddingGenerator
from semantic_core.database import create_vector_table, create_fts_table
from domain.models import Note, Category, Tag, NoteTag


def initialize_database():
    """Инициализирует БД и создает все таблицы."""
    print("🔧 Инициализация базы данных...")
    
    # Подключаемся к БД
    db = init_database()
    db.connect()
    
    # Создаем обычные таблицы
    db.create_tables([Category, Tag, Note, NoteTag], safe=True)
    
    # Создаем виртуальные таблицы для поиска
    create_vector_table(Note)
    create_fts_table(Note, text_columns=["title", "content"])
    
    print("✅ База данных готова!\n")
    return db


def seed_data():
    """Заполняет БД тестовыми данными."""
    print("🌱 Заполнение тестовыми данными...")
    
    # Создаем категории
    cat_python = Category.create(name="Python")
    cat_recipes = Category.create(name="Рецепты")
    cat_ideas = Category.create(name="Идеи")
    
    # Создаем теги
    tag_code = Tag.create(name="#код")
    tag_urgent = Tag.create(name="#срочно")
    tag_tasty = Tag.create(name="#вкусно")
    
    # Создаем заметки
    notes_data = [
        {
            "title": "Циклы в Python",
            "content": "В Python есть два основных цикла: for и while. Цикл for используется для итерации по последовательностям.",
            "category": cat_python,
            "tags": [tag_code]
        },
        {
            "title": "Работа со списками",
            "content": "Списки в Python - это мутабельные последовательности. Можно использовать list comprehension для создания списков.",
            "category": cat_python,
            "tags": [tag_code]
        },
        {
            "title": "Скрипт обработки данных",
            "content": "Срочно написать скрипт для парсинга CSV файлов и загрузки в базу данных.",
            "category": cat_python,
            "tags": [tag_code, tag_urgent]
        },
        {
            "title": "Борщ украинский",
            "content": "Классический рецепт борща: свекла, капуста, картофель, мясо. Варить 2-3 часа на медленном огне.",
            "category": cat_recipes,
            "tags": [tag_tasty]
        },
        {
            "title": "Паста Карбонара",
            "content": "Итальянская паста с беконом, яйцами и сыром пармезан. Готовится за 20 минут.",
            "category": cat_recipes,
            "tags": [tag_tasty]
        },
        {
            "title": "Идея проекта: Персональный ассистент",
            "content": "Разработать AI-помощника для управления задачами и заметками с семантическим поиском.",
            "category": cat_ideas,
            "tags": []
        },
        {
            "title": "Улучшение алгоритма поиска",
            "content": "Внедрить гибридный поиск, комбинирующий векторный и полнотекстовый подходы для лучших результатов.",
            "category": cat_ideas,
            "tags": [tag_urgent]
        },
    ]
    
    generator = EmbeddingGenerator()
    
    for note_data in notes_data:
        tags = note_data.pop("tags")
        note = Note.create(**note_data)
        
        # Добавляем теги
        for tag in tags:
            NoteTag.create(note=note, tag=tag)
        
        # Индексируем
        note.update_vector_index(generator)
        print(f"  ✓ Создана заметка: {note.title}")
    
    print(f"✅ Создано {len(notes_data)} заметок\n")


def test_vector_search():
    """Тест 1: Чистый векторный поиск."""
    print("🔍 Тест 1: Векторный поиск")
    print("Запрос: 'Как написать цикл?'")
    
    results = Note.vector_search("Как написать цикл?", limit=3)
    
    print(f"Найдено: {len(results)} результатов")
    for i, note in enumerate(results, 1):
        print(f"  {i}. {note.title} (Категория: {note.category.name})")
    print()


def test_fulltext_search():
    """Тест 2: Полнотекстовый поиск."""
    print("🔎 Тест 2: Полнотекстовый поиск")
    print("Запрос: 'скрипт'")
    
    results = Note.fulltext_search("скрипт", limit=3)
    
    print(f"Найдено: {len(results)} результатов")
    for i, note in enumerate(results, 1):
        print(f"  {i}. {note.title}")
    print()


def test_faceted_search():
    """Тест 3: Поиск с фильтром по категории."""
    print("🎯 Тест 3: Фасетный поиск (с фильтром)")
    print("Запрос: 'вкусный рецепт' в категории 'Рецепты'")
    
    cat_recipes = Category.get(Category.name == "Рецепты")
    results = Note.hybrid_search(
        "вкусный рецепт",
        limit=3,
        category=cat_recipes.id
    )
    
    print(f"Найдено: {len(results)} результатов")
    for i, note in enumerate(results, 1):
        print(f"  {i}. {note.title}")
    print()


def test_hybrid_search():
    """Тест 4: Гибридный поиск с RRF."""
    print("⚡ Тест 4: Гибридный поиск (RRF)")
    print("Запрос: 'срочный скрипт'")
    
    results = Note.hybrid_search("срочный скрипт", limit=5)
    
    print(f"Найдено: {len(results)} результатов")
    for i, note in enumerate(results, 1):
        tags = ", ".join(nt.tag.name for nt in note.note_tags)
        print(f"  {i}. {note.title} [{tags}]")
    print()


def main():
    """Основной сценарий тестирования."""
    print("=" * 60)
    print("🚀 POC: Семантический поиск на SQLite + Vec + Gemini")
    print("=" * 60)
    print()
    
    # Инициализация
    db = initialize_database()
    
    # Очистка и заполнение данных
    if Note.select().count() == 0:
        seed_data()
    else:
        print("ℹ️  База уже содержит данные, пропускаем seed\n")
    
    # Запускаем тесты
    test_vector_search()
    test_fulltext_search()
    test_faceted_search()
    test_hybrid_search()
    
    print("=" * 60)
    print("✅ Все тесты выполнены!")
    print("=" * 60)
    
    # Закрываем соединение
    db.close()


if __name__ == "__main__":
    main()
