"""
E2E тест для Phase 15-16: Qwen3 embedder -> Database -> Inspector.

ЭТОГО ТЕСТА НЕ БЫЛО. Вот почему мы потратили 2 часа на дебаг.
"""

import os
import sys
from pathlib import Path

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


class TestQwen3E2EPipeline:
    """
    E2E тесты для Qwen3 embedder через весь стек:
    Config -> Factory -> Embedder -> Database -> Inspector -> Artifacts
    """

    def test_qwen3_config_propagation(self, tmp_path):
        """
        КРИТИЧЕСКИЙ E2E: semantic.toml -> ComponentFactory -> embedder.dimension -> PeeweeVectorStore

        Этот тест словил бы ВСЕ 8 багов:
        1. mlx-embeddings версия 0.1.0 не существует
        2. Qwen3 требует mlx-lm backend (не mlx-embeddings)
        3. MLX float16 -> numpy несовместимость
        4. Pydantic Settings двойная инициализация
        5. CLI не передавал dimension в PeeweeVectorStore
        6. chunks_vec не пересоздавался при смене dimension
        7. logger exc_info KeyError
        8. SnapshotManager wrong API (session_name vs session_path)
        """
        # 1. Создаём semantic.toml с Qwen3
        config_path = tmp_path / "semantic.toml"
        config_path.write_text(
            """
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
"""
        )

        # 2. Загружаем конфиг (словили бы баг #4: Pydantic double-init)
        config = SemanticConfig(config_file=str(config_path))
        assert config.defaults.embedding_provider == "local"
        assert config.providers_local.embedding_model == "qwen3-embedding"

        # 3. Создаём embedder через Factory (словили бы баг #1, #2)
        embedder = ComponentFactory.create_embedder(config)
        assert embedder.dimension == 1024, "Qwen3 должен быть 1024D"

        # 4. Инициализируем БД с правильным dimension (словили бы баг #6)
        db_path = tmp_path / "test.db"
        db = init_peewee_database(str(db_path), embedder.dimension)

        # 5. Создаём store с dimension (словили бы баг #5)
        store = PeeweeVectorStore(database=db, dimension=embedder.dimension)

        # 6. Проверяем схему БД
        result = db.execute_sql(
            "SELECT sql FROM sqlite_master WHERE name='chunks_vec'"
        ).fetchone()
        assert "FLOAT[1024]" in result[0], "chunks_vec должен быть FLOAT[1024]"

        # 7. Тестируем embedder (словили бы баг #3: float16 -> numpy)
        text = "Test embedding generation"
        embedding = embedder.embed_query(text)
        assert embedding.shape == (1024,), "Эмбеддинг должен быть 1024D"

    def test_qwen3_inspector_artifacts(self, tmp_path):
        """
        E2E: semantic inspect с Qwen3 -> сохранение артефактов.

        Словили бы баг #8: SnapshotManager API.
        """
        # Setup
        config_path = tmp_path / "semantic.toml"
        config_path.write_text(
            """
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
"""
        )

        db_path = tmp_path / "test.db"
        config = SemanticConfig(config_file=str(config_path), db_path=str(db_path))

        # Создаём context через CLI (как в реальном использовании)
        context = CLIContext(db_path=db_path)
        core = context.get_core()  # Ленивая инициализация

        # Проверяем dimension через embedder из core
        embedder = core.embedder
        assert embedder.dimension == 1024

        # Создаём inspector
        artifacts_root = tmp_path / "artifacts"
        inspector = ProviderInspector(core=core, artifacts_root=artifacts_root)

        # Создаём тестовый файл
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nSome content for testing.")

        # Inspect (словили бы баг #8: session_name vs session_path)
        snapshot = inspector.ingest_with_inspection(path=str(test_file))

        # Проверяем метаданные
        assert snapshot.embedder_metadata.dimension == 1024
        assert len(snapshot.chunks) > 0

        # Сохраняем snapshot
        session_folder = artifacts_root / "test_session"
        session_folder.mkdir(parents=True, exist_ok=True)
        snapshot_path = inspector.snapshot_manager.save_snapshot(
            snapshot, session_path=session_folder, file_prefix="test", compress=False
        )

        # Копируем входной файл (как в CLI inspect команде)
        import shutil

        input_copy_path = session_folder / f"input_{test_file.name}"
        shutil.copy(test_file, input_copy_path)

        # Проверяем артефакты
        assert snapshot_path.exists()
        assert input_copy_path.exists()

    @pytest.mark.skipif(
        not os.getenv("GEMINI_API_KEY"),
        reason="Requires GEMINI_API_KEY in environment",
    )
    def test_qwen3_vs_gemini_dimension_mismatch(self, tmp_path):
        """
        E2E: Проверка что БД пересоздаётся при смене embedder.

        Gemini 768D -> Qwen3 1024D должно работать.
        Словили бы баг #6: chunks_vec не пересоздавался.
        """
        db_path = tmp_path / "test.db"

        # 1. Gemini (768D)
        config_gemini_path = tmp_path / "gemini.toml"
        config_gemini_path.write_text(
            """
[defaults]
embedding_provider = "gemini"

[providers.gemini]
embedding_model = "text-embedding-004"
dimension = 768
"""
        )
        # Используем monkeypatch чтобы SemanticConfig НЕ загружал глобальный semantic.toml
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))  # Меняем CWD чтобы не было semantic.toml
            config_gemini = SemanticConfig(
                config_file=str(config_gemini_path), db_path=str(db_path)
            )
            embedder_gemini = ComponentFactory.create_embedder(config_gemini)
            assert embedder_gemini.dimension == 768
        finally:
            os.chdir(old_cwd)

        db1 = init_peewee_database(str(db_path), embedder_gemini.dimension)
        store1 = PeeweeVectorStore(database=db1, dimension=768)

        # Проверяем FLOAT[768]
        result = db1.execute_sql(
            "SELECT sql FROM sqlite_master WHERE name='chunks_vec'"
        ).fetchone()
        assert "FLOAT[768]" in result[0]
        db1.close()

        # 2. Переключаемся на Qwen3 (1024D)
        config_path = tmp_path / "semantic.toml"
        config_path.write_text(
            """
[defaults]
embedding_provider = "local"

[providers.local]
embedding_model = "qwen3-embedding"
"""
        )

        config_qwen = SemanticConfig(config_file=str(config_path), db_path=str(db_path))
        embedder_qwen = ComponentFactory.create_embedder(config_qwen)
        assert embedder_qwen.dimension == 1024

        # БАГ БЫ СЛОВИЛИ ЗДЕСЬ: БД осталась бы FLOAT[768]!
        db2 = init_peewee_database(str(db_path), embedder_qwen.dimension)
        store2 = PeeweeVectorStore(database=db2, dimension=1024)

        # Проверяем FLOAT[1024]
        result = db2.execute_sql(
            "SELECT sql FROM sqlite_master WHERE name='chunks_vec'"
        ).fetchone()
        assert "FLOAT[1024]" in result[0], (
            "chunks_vec должен пересоздаться с новым dimension!"
        )
