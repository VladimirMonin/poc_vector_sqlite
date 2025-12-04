"""Тесты загрузки и управления документами.

Проверяет:
- UploadService: сохранение, валидация, пути
- Ingest routes: upload, documents, delete
"""

import io
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ============================================================================
# UploadService Tests
# ============================================================================


class TestUploadService:
    """Тесты UploadService."""

    @pytest.fixture
    def upload_service(self, tmp_path):
        """UploadService с временной директорией."""
        from app.services.upload_service import UploadService

        return UploadService(upload_dir=tmp_path)

    def test_init_creates_directory(self, tmp_path):
        """Инициализация создаёт директорию uploads."""
        from app.services.upload_service import UploadService

        upload_dir = tmp_path / "new_uploads"
        assert not upload_dir.exists()

        service = UploadService(upload_dir=upload_dir)

        assert upload_dir.exists()

    def test_save_file_success(self, upload_service, tmp_path):
        """Успешное сохранение файла."""
        content = b"# Test Markdown\n\nHello World"
        file_data = io.BytesIO(content)

        result = upload_service.save_file(file_data, "test.md")

        assert result.success is True
        assert result.path is not None
        assert result.path.exists()
        assert result.original_name == "test.md"
        assert result.uuid_name is not None
        assert "_test.md" in result.uuid_name

    def test_save_file_content_preserved(self, upload_service):
        """Содержимое файла сохраняется корректно."""
        content = b"# Hello\n\nWorld"
        file_data = io.BytesIO(content)

        result = upload_service.save_file(file_data, "doc.md")

        saved_content = result.path.read_bytes()
        assert saved_content == content

    def test_save_file_disallowed_extension(self, upload_service):
        """Неподдерживаемое расширение отклоняется."""
        file_data = io.BytesIO(b"binary data")

        result = upload_service.save_file(file_data, "script.exe")

        assert result.success is False
        assert result.path is None
        assert ".exe" in result.error

    def test_save_file_allowed_extensions(self, upload_service):
        """Проверка поддерживаемых расширений."""
        allowed = [".md", ".png", ".jpg", ".mp3", ".mp4"]

        for ext in allowed:
            file_data = io.BytesIO(b"test content")
            result = upload_service.save_file(file_data, f"file{ext}")
            assert result.success is True, f"Extension {ext} should be allowed"

    def test_uuid_name_unique(self, upload_service):
        """Каждый файл получает уникальный UUID."""
        results = []
        for i in range(3):
            file_data = io.BytesIO(b"content")
            result = upload_service.save_file(file_data, "same_name.md")
            results.append(result.uuid_name)

        # Все UUID должны быть уникальны
        assert len(set(results)) == 3

    def test_delete_file_success(self, upload_service):
        """Успешное удаление файла."""
        # Создаём файл
        file_data = io.BytesIO(b"content")
        result = upload_service.save_file(file_data, "test.md")
        assert result.path.exists()

        # Удаляем
        deleted = upload_service.delete_file(result.uuid_name)

        assert deleted is True
        assert not result.path.exists()

    def test_delete_file_not_found(self, upload_service):
        """Удаление несуществующего файла."""
        deleted = upload_service.delete_file("nonexistent.md")

        assert deleted is False

    def test_list_files(self, upload_service):
        """Получение списка файлов."""
        # Создаём файлы
        for i in range(3):
            file_data = io.BytesIO(b"content")
            upload_service.save_file(file_data, f"file{i}.md")

        files = upload_service.list_files()

        assert len(files) == 3
        assert all("name" in f and "size" in f for f in files)

    def test_process_markdown_paths(self, upload_service, tmp_path):
        """Обновление путей в Markdown."""
        # Создаём Markdown с относительными путями
        md_content = "![alt](images/photo.png)\n[link](docs/file.pdf)"
        md_path = tmp_path / "test.md"
        md_path.write_text(md_content)

        # Маппинг загруженных файлов
        uploaded_files = {
            "photo.png": Path("/uploads/abc123_photo.png"),
        }

        result = upload_service.process_markdown_paths(md_path, uploaded_files)

        # Windows использует backslash, проверяем что путь заменён
        assert "abc123_photo.png" in result
        # Несуществующий файл не меняется
        assert "docs/file.pdf" in result


# ============================================================================
# Ingest Routes Tests
# ============================================================================


class TestIngestRoutes:
    """Тесты маршрутов загрузки."""

    def test_upload_page_loads(self, client):
        """Страница загрузки открывается."""
        response = client.get("/ingest")

        assert response.status_code == 200
        assert (
            b"upload" in response.data.lower()
            or b"\xd0\xb7\xd0\xb0\xd0\xb3\xd1\x80\xd1\x83\xd0\xb7"
            in response.data.lower()
        )

    def test_upload_page_without_core(self, app, client):
        """Страница показывает предупреждение без core."""
        with app.app_context():
            app.extensions["semantic_core"] = None

            response = client.get("/ingest")

            assert response.status_code == 200
            assert b"alert" in response.data

    def test_documents_page_loads(self, client):
        """Страница документов открывается."""
        response = client.get("/documents")

        assert response.status_code == 200

    def test_documents_page_shows_table(self, client):
        """Страница документов показывает таблицу."""
        response = client.get("/documents")

        assert response.status_code == 200
        # Должна быть таблица документов или сообщение о пустом списке
        assert (
            b"documents-table" in response.data  # Таблица документов
            or b"inbox" in response.data.lower()  # Пустой inbox
            or b"\xd0\xbd\xd0\xb5\xd1\x82" in response.data.lower()  # "нет" по-русски
        )

    def test_upload_no_files(self, client):
        """Загрузка без файлов показывает предупреждение."""
        response = client.post("/ingest/upload", data={})

        # Редирект на страницу загрузки
        assert response.status_code == 302

    def test_upload_with_file(self, app, client):
        """Загрузка файла (с mock core)."""
        with app.app_context():
            # Mock core
            mock_core = MagicMock()
            app.extensions["semantic_core"] = mock_core

            # Создаём тестовый файл
            data = {
                "files": (io.BytesIO(b"# Test\n\nContent"), "test.md"),
            }

            response = client.post(
                "/ingest/upload",
                data=data,
                content_type="multipart/form-data",
            )

            # Редирект на документы
            assert response.status_code == 302

    def test_delete_document_without_core(self, app, client):
        """Удаление без core возвращает ошибку."""
        with app.app_context():
            app.extensions["semantic_core"] = None

            response = client.post(
                "/documents/1/delete",
                headers={"HX-Request": "true"},
            )

            assert response.status_code == 500


# ============================================================================
# UploadResult Tests
# ============================================================================


class TestUploadResult:
    """Тесты UploadResult dataclass."""

    def test_success_result(self):
        """Успешный результат содержит path."""
        from app.services.upload_service import UploadResult

        result = UploadResult(
            success=True,
            path=Path("/uploads/test.md"),
            original_name="test.md",
            uuid_name="abc123_test.md",
        )

        assert result.success is True
        assert result.path is not None
        assert result.error is None

    def test_error_result(self):
        """Неуспешный результат содержит error."""
        from app.services.upload_service import UploadResult

        result = UploadResult(
            success=False,
            path=None,
            original_name="test.exe",
            uuid_name=None,
            error="Extension not allowed",
        )

        assert result.success is False
        assert result.path is None
        assert result.error is not None


# ============================================================================
# Integration Tests
# ============================================================================


class TestIngestIntegration:
    """Интеграционные тесты загрузки."""

    def test_upload_creates_file_on_disk(self, app, client, tmp_path):
        """Загрузка создаёт файл на диске."""
        with app.app_context():
            # Mock core
            mock_core = MagicMock()
            app.extensions["semantic_core"] = mock_core

            # Устанавливаем instance_path
            app.instance_path = str(tmp_path)

            data = {
                "files": (io.BytesIO(b"# Hello\n"), "hello.md"),
            }

            client.post(
                "/ingest/upload",
                data=data,
                content_type="multipart/form-data",
            )

            # Проверяем, что файл создан
            uploads_dir = tmp_path / "uploads"
            assert uploads_dir.exists()
            files = list(uploads_dir.glob("*_hello.md"))
            assert len(files) == 1

    def test_multiple_files_upload(self, app, client, tmp_path):
        """Загрузка нескольких файлов."""
        with app.app_context():
            mock_core = MagicMock()
            app.extensions["semantic_core"] = mock_core
            app.instance_path = str(tmp_path)

            data = {
                "files": [
                    (io.BytesIO(b"# Doc 1"), "doc1.md"),
                    (io.BytesIO(b"# Doc 2"), "doc2.md"),
                    (io.BytesIO(b"image data"), "image.png"),
                ],
            }

            client.post(
                "/ingest/upload",
                data=data,
                content_type="multipart/form-data",
            )

            uploads_dir = tmp_path / "uploads"
            assert len(list(uploads_dir.iterdir())) == 3
