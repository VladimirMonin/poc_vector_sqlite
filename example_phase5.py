"""Пример использования Phase 5: Async Batching.

Демонстрирует:
- Настройку GoogleKeyring с разделением ключей.
- Асинхронный режим ingest (mode='async').
- Управление батч-очередью через BatchManager.
- Синхронизацию статусов и скачивание результатов.
"""

from semantic_core import (
    SemanticCore,
    BatchManager,
    GoogleKeyring,
    Document,
    GeminiEmbedder,
    PeeweeVectorStore,
    init_peewee_database,
)
from semantic_core.processing import SmartSplitter, HierarchicalContextStrategy


def main():
    """Демонстрация работы с асинхронной батч-обработкой."""

    # === 1. Настройка ключей с разделением биллинга ===
    keyring = GoogleKeyring(
        default_key="YOUR_DEFAULT_KEY",  # Для синхронных операций
        batch_key="YOUR_BATCH_KEY",  # Для батч-обработки (50% скидка)
    )

    # === 2. Инициализация компонентов ===
    db = init_peewee_database("data_phase5.db")

    embedder = GeminiEmbedder(
        api_key=keyring.default_key,
        dimension=768,
    )

    store = PeeweeVectorStore(db, dimension=768)

    # SmartSplitter требует parser и правильные имена параметров
    from semantic_core.processing.parsers import MarkdownNodeParser
    parser = MarkdownNodeParser()

    splitter = SmartSplitter(
        parser=parser,
        chunk_size=500,        # Размер текстового чанка в символах
        code_chunk_size=1000,  # Размер чанка кода в символах
        preserve_code=True,    # Изолировать блоки кода
    )

    context_strategy = HierarchicalContextStrategy()

    # === 3. Создание ядра и менеджера ===
    core = SemanticCore(
        embedder=embedder,
        store=store,
        splitter=splitter,
        context_strategy=context_strategy,
    )

    batch_manager = BatchManager(
        keyring=keyring,
        vector_store=store,
        dimension=768,
    )

    # === 4. Асинхронная загрузка документов ===
    print("\n=== Загрузка документов в async режиме ===")

    documents = [
        Document(
            content="# Python Tutorial\n\nPython is a high-level language...",
            metadata={"title": "Python Basics", "category": "tutorial"},
        ),
        Document(
            content="# ML Overview\n\nMachine Learning algorithms...",
            metadata={"title": "ML Guide", "category": "tutorial"},
        ),
        Document(
            content="# Data Science\n\nData analysis with pandas...",
            metadata={"title": "DS Intro", "category": "tutorial"},
        ),
    ]

    for doc in documents:
        saved = core.ingest(doc, mode="async")  # 🔥 Async режим!
        print(f"✓ Документ '{doc.metadata['title']}' сохранён (ID: {saved.id})")
        print(f"  Чанки в статусе PENDING, векторы будут созданы позже")

    # === 5. Проверка очереди ===
    print("\n=== Статистика очереди ===")
    stats = batch_manager.get_queue_stats()
    print(f"Pending: {stats['pending']}")
    print(f"Processing: {stats['processing']}")
    print(f"Ready: {stats['ready']}")
    print(f"Failed: {stats['failed']}")

    # === 6. Отправка батча на обработку ===
    print("\n=== Отправка батча в Google ===")
    batch_id = batch_manager.flush_queue(min_size=3, force=True)

    if batch_id:
        print(f"✓ Батч {batch_id[:8]}... отправлен в Google")
        print(f"  Статус можно проверить через sync_status()")

    # === 7. Синхронизация (обычно запускается позже, через cron) ===
    print("\n=== Проверка статуса (имитация) ===")
    print("В продакшене:")
    print("1. Запускайте sync_status() периодически (каждые 5-10 минут)")
    print("2. Когда статус COMPLETED, векторы автоматически обновятся в БД")
    print("3. Можно использовать обычный search() для поиска")

    # Пример вызова:
    # statuses = batch_manager.sync_status()
    # print(statuses)  # {'batch_id': 'PROCESSING'}

    # === 8. Поиск (работает только с READY чанками) ===
    print("\n=== Поиск документов ===")
    print("После завершения батча можно искать как обычно:")
    print("results = core.search('Python programming')")

    db.close()
    print("\n✓ Демонстрация завершена")


if __name__ == "__main__":
    main()
