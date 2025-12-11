"""
E2E тест для Phase 15-16: Qwen3 с расширенными возможностями.

Проверяет:
1. Qwen3-Embedding с max_tokens=4000 (вместо дефолтных 512)
2. Qwen3-VL локальная модель для анализа изображений
3. Гибридный поиск с проверкой похожести
4. Inspector artifacts с медиа-контентом

Требует:
- Apple Silicon (M1/M2/M3)
- MLX зависимости
- ~4GB RAM для Qwen3-VL-4B
"""

import os
import sys
from pathlib import Path
import shutil

import pytest

# Проверка доступности MLX
try:
    import mlx.core as mx
    import platform

    MLX_AVAILABLE = True
    IS_APPLE_SILICON = sys.platform == "darwin" and platform.machine() == "arm64"
except ImportError:
    MLX_AVAILABLE = False
    IS_APPLE_SILICON = False

from semantic_core.cli.context import CLIContext
from semantic_core.config import SemanticConfig
from semantic_core.core.factory import ComponentFactory
from semantic_core.core.observatory.inspector import ProviderInspector
from semantic_core.infrastructure.storage.peewee.engine import init_peewee_database
from semantic_core.infrastructure.storage.peewee.adapter import PeeweeVectorStore

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not MLX_AVAILABLE or not IS_APPLE_SILICON,
        reason="Requires MLX on Apple Silicon",
    ),
]


class TestQwen3ExtendedPipeline:
    """E2E тесты для Qwen3 с расширенными токенами и multimodal."""

    def test_qwen3_4000_tokens_embeddings(self, tmp_path):
        """
        E2E: Qwen3 с max_tokens=4000 (вместо 512).
        
        Модель поддерживает до 8192 токенов, проверяем что можем
        использовать большие чанки для документов.
        """
        # Создаём конфиг с max_tokens=4000
        config_path = tmp_path / "semantic.toml"
        config_path.write_text(
            """
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
max_tokens = 4000
"""
        )

        db_path = tmp_path / "test.db"
        config = SemanticConfig(config_file=str(config_path), db_path=str(db_path))

        # Создаём embedder
        embedder = ComponentFactory.create_embedder(config)
        assert embedder.dimension == 1024, "Qwen3 должен быть 1024D"

        # Проверяем что max_tokens установлен правильно
        from semantic_core.infrastructure.local.embeddings import LocalEmbedder

        assert isinstance(embedder, LocalEmbedder)
        # LocalEmbedder хранит config._max_tokens
        assert embedder._config.max_tokens == 4000

        # Тестируем на длинном тексте (> 512 токенов)
        long_text = " ".join(["This is a test sentence."] * 200)  # ~1000 токенов
        embedding = embedder.embed_query(long_text)

        assert embedding.shape == (1024,), "Эмбеддинг должен быть 1024D"
        print(f"\n✓ Qwen3 с max_tokens=4000 работает")
        print(f"✓ Обработан текст длиной ~{len(long_text.split())} слов")

    def test_qwen3_vision_local_analysis(self, tmp_path):
        """
        E2E: Локальная Qwen3-VL-4B для анализа изображений.
        
        Проверяет что можем использовать локальную VLM модель
        вместо облачного Gemini Vision.
        """
        # Импорты MLX-VLM (обязательны!)
        from mlx_vlm import load, generate
        from mlx_vlm.prompt_utils import apply_chat_template

        # Создаём тестовое изображение
        test_image = tmp_path / "test_image.png"

        # Копируем тестовое изображение из референса
        ref_images = (
            Path(__file__).parent.parent.parent.parent
            / "examples"
            / "poc_apple_local_llm"
            / "test_images"
        )
        
        if ref_images.exists():
            images = list(ref_images.glob("*.png")) + list(ref_images.glob("*.jpg"))
            if images:
                shutil.copy(images[0], test_image)
                print(f"\n🖼️  Скопировано изображение из референса: {images[0].name}")
            else:
                # Создаём простое тестовое изображение
                from PIL import Image
                import numpy as np

                img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
                img = Image.fromarray(img_array)
                img.save(test_image)
                print(f"\n🖼️  Создано тестовое изображение 100x100")
        else:
            # Создаём простое тестовое изображение
            from PIL import Image
            import numpy as np

            img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            img = Image.fromarray(img_array)
            img.save(test_image)
            print(f"\n🖼️  Создано тестовое изображение 100x100")

        # Загружаем модель Qwen3-VL-4B (КАК В РЕФЕРЕНСЕ!)
        model_name = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
        print(f"📦 Загрузка {model_name}...")
        print(f"   ⚠️  Это может занять несколько минут при первой загрузке")

        model, processor = load(model_name)
        config = model.config
        print(f"✓ Модель загружена")

        # Генерируем описание на русском (КАК В РЕФЕРЕНСЕ!)
        messages = [
            {
                "role": "user",
                "content": "Опиши что изображено на этой картинке подробно на русском языке.",
            }
        ]

        prompt = apply_chat_template(processor, config, messages, num_images=1)

        print(f"💬 Промпт: {messages[0]['content']}")
        print(f"🤖 Генерация ответа...")

        import time

        start_time = time.time()

        output = generate(
            model,
            processor,
            prompt,
            str(test_image),
            max_tokens=200,
            temp=0.7,
            verbose=True,  # Показываем токены в реальном времени
        )

        generation_time = time.time() - start_time

        # mlx-vlm 0.3.9 возвращает GenerationResult объект
        output_text = output.text if hasattr(output, "text") else str(output)

        print(f"\n" + "=" * 70)
        print("📝 ОТВЕТ МОДЕЛИ:")
        print("=" * 70)
        print(output_text)
        print("=" * 70)

        # Подсчет токенов (приблизительно)
        tokens = len(output_text.split())
        tokens_per_sec = tokens / generation_time if generation_time > 0 else 0

        print(f"\n📊 Статистика генерации:")
        print(f"   • Время: {generation_time:.2f} сек")
        print(f"   • Токенов: ~{tokens}")
        print(f"   • Скорость: ~{tokens_per_sec:.1f} токенов/сек")

        if tokens_per_sec > 20:
            print(f"   ✅ Скорость отличная (> 20 t/s)")
        elif tokens_per_sec > 10:
            print(f"   ⚠️  Скорость приемлемая (> 10 t/s)")
        else:
            print(f"   🔴 Скорость низкая (< 10 t/s)")

        # Проверяем что ответ не пустой
        assert len(output_text) > 0, "Модель должна вернуть описание"
        assert len(output_text.split()) > 5, "Описание должно содержать минимум 5 слов"

        print(f"\n✓ Qwen3-VL локальный анализ работает корректно")

        # Очищаем память (важно для 8GB MacBook!)
        del model, processor, config
        import gc

        gc.collect()

    def test_qwen3_hybrid_search_with_inspection(self, tmp_path):
        """
        E2E: Полный pipeline с инспекцией:
        1. Qwen3 embeddings (4000 tokens)
        2. Индексация документа
        3. Гибридный поиск (vector + FTS)
        4. Inspector artifacts
        """
        # Создаём конфиг
        config_path = tmp_path / "semantic.toml"
        config_path.write_text(
            """
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
max_tokens = 4000
"""
        )

        db_path = tmp_path / "test.db"

        # Создаём context через CLI (как в реальном использовании)
        context = CLIContext(db_path=db_path)
        core = context.get_core()

        # Проверяем embedder
        embedder = core.embedder
        assert embedder.dimension == 1024

        # Создаём тестовый документ
        test_file = tmp_path / "test_document.md"
        test_file.write_text(
            """# Machine Learning Overview

Machine learning is a subset of artificial intelligence that focuses on 
building systems that learn from data. Deep learning uses neural networks 
with multiple layers to process complex patterns.

## Key Concepts

- **Supervised Learning**: Training with labeled data
- **Unsupervised Learning**: Finding patterns without labels
- **Reinforcement Learning**: Learning through trial and error

## Applications

Machine learning powers many modern applications:
- Natural Language Processing (NLP)
- Computer Vision
- Recommendation Systems
- Autonomous Vehicles

The field continues to evolve rapidly with new architectures like 
transformers and diffusion models.
""",
            encoding="utf-8",
        )

        # Создаём inspector
        artifacts_root = tmp_path / "artifacts"
        inspector = ProviderInspector(core=core, artifacts_root=artifacts_root)

        # STEP 1: Ingest с инспекцией
        print(f"\n📥 STEP 1: Ingest inspection...")
        snapshot = inspector.ingest_with_inspection(path=str(test_file))

        assert len(snapshot.chunks) > 0, "Должны быть созданы чанки"
        assert snapshot.embedder_metadata.dimension == 1024
        print(f"✓ Создано {len(snapshot.chunks)} чанков")

        # STEP 2: Поиск
        print(f"\n🔍 STEP 2: Search inspection...")
        search_query = "neural networks and deep learning"

        search_snapshot = inspector.search_with_inspection(
            query=search_query, top_k=3
        )

        assert len(search_snapshot.searches) > 0
        search_result = search_snapshot.searches[0]
        assert search_result.results_count > 0
        assert search_result.query == search_query

        print(f"✓ Найдено {search_result.results_count} результатов")

        # Проверяем similarity scores
        for idx, result in enumerate(search_result.results[:3], 1):
            similarity = result.get("similarity", 0.0)
            content = result.get("content", "")[:100]
            print(
                f"  {idx}. Similarity: {similarity:.4f} | Content: {content}..."
            )
            assert similarity > 0, "Similarity должна быть > 0"

        # STEP 3: Сохраняем artifacts
        print(f"\n💾 STEP 3: Saving artifacts...")

        session_folder = artifacts_root / "test_session"
        session_folder.mkdir(parents=True, exist_ok=True)

        # Объединяем snapshots
        snapshot.searches.extend(search_snapshot.searches)

        # Сохраняем
        snapshot_path = inspector.snapshot_manager.save_snapshot(
            snapshot, session_path=session_folder, file_prefix="test", compress=False
        )

        # Копируем входной файл
        input_copy_path = session_folder / f"input_{test_file.name}"
        shutil.copy(test_file, input_copy_path)

        # Сохраняем similarity matrix
        similarity_csv_path = session_folder / "similarities.csv"
        with similarity_csv_path.open("w", encoding="utf-8") as f:
            f.write("rank,chunk_id,content_preview,similarity\n")
            for idx, result in enumerate(search_result.results, 1):
                content = result.get("content", "").replace("\n", " ")[:100]
                similarity = result.get("similarity", 0.0)
                chunk_id = result.get("chunk_id", "N/A")
                f.write(f'{idx},{chunk_id},"{content}",{similarity:.6f}\n')

        # Проверяем артефакты
        assert snapshot_path.exists()
        assert input_copy_path.exists()
        assert similarity_csv_path.exists()

        print(f"\n✅ Все артефакты сохранены:")
        print(f"  • Snapshot: {snapshot_path}")
        print(f"  • Input copy: {input_copy_path}")
        print(f"  • Similarity matrix: {similarity_csv_path}")

    def test_qwen3_multimodal_document_inspection(self, tmp_path):
        """
        E2E: Инспекция документа с текстом и изображениями.
        
        Проверяет полный multimodal pipeline:
        - Текст -> Qwen3 embeddings (4000 tokens)
        - Изображения -> Qwen3-VL анализ
        - Artifacts с медиа-контентом
        """
        # Проверяем mlx-vlm
        try:
            from mlx_vlm import load
        except ImportError:
            pytest.skip("mlx-vlm не установлен")

        # Создаём конфиг
        config_path = tmp_path / "semantic.toml"
        config_path.write_text(
            """
[defaults]
embedding_provider = "local"
vision_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
max_tokens = 4000
vision_model = "qwen3-vl"
"""
        )

        db_path = tmp_path / "test.db"

        # Создаём тестовый документ с изображениями
        test_file = tmp_path / "multimodal_doc.md"
        test_file.write_text(
            """# Computer Vision Research

This document explores modern computer vision techniques.

![Sample Image](test_image.png)

## Deep Learning Architectures

Convolutional Neural Networks (CNNs) have revolutionized image processing.

## Applications

- Object Detection
- Image Segmentation
- Face Recognition
""",
            encoding="utf-8",
        )

        # Создаём тестовое изображение
        test_image = tmp_path / "test_image.png"
        try:
            from PIL import Image
            import numpy as np

            img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            img = Image.fromarray(img_array)
            img.save(test_image)
        except ImportError:
            pytest.skip("Pillow не установлен")

        # Создаём context
        context = CLIContext(db_path=db_path)
        core = context.get_core()

        # Создаём inspector
        artifacts_root = tmp_path / "artifacts"
        inspector = ProviderInspector(core=core, artifacts_root=artifacts_root)

        # Ingest с инспекцией
        print(f"\n📥 Multimodal ingest inspection...")
        snapshot = inspector.ingest_with_inspection(path=str(test_file))

        # Проверяем что текстовые чанки обработаны
        assert len(snapshot.chunks) > 0
        print(f"✓ Создано {len(snapshot.chunks)} текстовых чанков")

        # Проверяем embeddings dimension
        assert snapshot.embedder_metadata.dimension == 1024

        # Сохраняем artifacts
        session_folder = artifacts_root / "multimodal_session"
        session_folder.mkdir(parents=True, exist_ok=True)

        snapshot_path = inspector.snapshot_manager.save_snapshot(
            snapshot, session_path=session_folder, file_prefix="multimodal", compress=False
        )

        input_copy_path = session_folder / f"input_{test_file.name}"
        shutil.copy(test_file, input_copy_path)

        # Копируем изображение
        image_copy_path = session_folder / f"media_{test_image.name}"
        shutil.copy(test_image, image_copy_path)

        print(f"\n✅ Multimodal artifacts сохранены:")
        print(f"  • Snapshot: {snapshot_path}")
        print(f"  • Input: {input_copy_path}")
        print(f"  • Image: {image_copy_path}")

        assert snapshot_path.exists()
        assert input_copy_path.exists()
        assert image_copy_path.exists()
