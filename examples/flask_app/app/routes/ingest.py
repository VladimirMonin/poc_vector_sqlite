"""Ingest routes — загрузка и управление документами.

Blueprints:
    ingest_bp: Загрузка файлов, список документов, удаление.

Endpoints:
    GET /ingest — Страница загрузки
    POST /ingest/upload — Загрузка файлов
    GET /documents — Список документов
    POST /documents/<id>/delete — Удаление документа
    POST /documents/<id>/reindex — Переиндексация
"""

from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)

from app.services.upload_service import UploadService
from semantic_core.domain import Document
from semantic_core.infrastructure.storage.peewee.models import (
    DocumentModel,
    ChunkModel,
)
from semantic_core.utils.logger import get_logger

logger = get_logger("flask_app.routes.ingest")

ingest_bp = Blueprint("ingest", __name__)

# Порог для async processing
ASYNC_THRESHOLD = 5


def _get_upload_service() -> UploadService:
    """Получить UploadService из контекста приложения."""
    upload_dir = Path(current_app.instance_path) / "uploads"
    return UploadService(upload_dir=upload_dir)


def _get_document_stats(doc_id: int) -> dict:
    """Получить статистику чанков документа."""
    chunks = ChunkModel.select().where(ChunkModel.document_id == doc_id)
    
    stats = {
        "total": 0,
        "text": 0,
        "code": 0,
        "image": 0,
        "audio": 0,
        "pending": 0,
    }
    
    for chunk in chunks:
        stats["total"] += 1
        chunk_type = chunk.chunk_type
        if chunk_type == "text":
            stats["text"] += 1
        elif chunk_type == "code":
            stats["code"] += 1
        elif chunk_type == "image_ref":
            stats["image"] += 1
        elif chunk_type == "audio_ref":
            stats["audio"] += 1
        
        if chunk.embedding_status == "pending":
            stats["pending"] += 1
    
    return stats


@ingest_bp.route("/ingest")
def upload_page():
    """Страница загрузки файлов.

    Показывает drag-n-drop форму для загрузки.
    """
    core = current_app.extensions.get("semantic_core")

    return render_template(
        "ingest.html",
        core_available=core is not None,
    )


@ingest_bp.route("/ingest/upload", methods=["POST"])
def upload_files():
    """Загрузка файлов и индексация.

    Принимает multiple files, сохраняет в uploads/,
    запускает ingest() (sync или async).

    Returns:
        Redirect на страницу документов с flash-сообщением.
    """
    core = current_app.extensions.get("semantic_core")
    if not core:
        flash("SemanticCore недоступен. Проверьте API ключ.", "danger")
        return redirect(url_for("ingest.upload_page"))

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        flash("Файлы не выбраны", "warning")
        return redirect(url_for("ingest.upload_page"))

    upload_service = _get_upload_service()
    uploaded_files: dict[str, Path] = {}
    markdown_files: list[Path] = []
    errors: list[str] = []

    # Сохраняем все файлы
    for file in files:
        if file.filename:
            result = upload_service.save_file(file.stream, file.filename)
            if result.success:
                uploaded_files[result.original_name] = result.path
                if result.path.suffix.lower() in (".md", ".markdown"):
                    markdown_files.append(result.path)
            else:
                errors.append(f"{result.original_name}: {result.error}")

    if errors:
        for error in errors:
            flash(error, "danger")

    # Определяем режим (sync/async)
    mode = "async" if len(markdown_files) >= ASYNC_THRESHOLD else "sync"
    logger.info(f"📤 Загружено {len(files)} файлов, mode={mode}")

    # Индексируем Markdown-файлы
    ingested_count = 0
    for md_path in markdown_files:
        try:
            # Обновляем пути к медиа
            content = upload_service.process_markdown_paths(
                md_path,
                {Path(name).name: path for name, path in uploaded_files.items()},
            )

            # Создаём документ
            doc = Document(
                content=content,
                metadata={
                    "title": md_path.stem.replace("_", " ").title(),
                    "source": str(md_path),
                    "source_type": "upload",
                },
            )

            # Индексируем
            core.ingest(doc, mode=mode)
            ingested_count += 1

        except Exception as e:
            logger.error(f"🔥 Ошибка индексации {md_path}: {e}")
            flash(f"Ошибка индексации {md_path.name}: {e}", "danger")

    if ingested_count > 0:
        if mode == "async":
            flash(
                f"✅ Загружено {ingested_count} документов. "
                f"Обработка в фоновом режиме...",
                "info",
            )
        else:
            flash(f"✅ Загружено и проиндексировано {ingested_count} документов", "success")

    return redirect(url_for("ingest.documents_page"))


@ingest_bp.route("/documents")
def documents_page():
    """Страница списка документов.

    Показывает все документы с информацией о чанках.
    """
    core = current_app.extensions.get("semantic_core")

    # Получаем все документы
    documents = []
    for doc in DocumentModel.select().order_by(DocumentModel.created_at.desc()):
        stats = _get_document_stats(doc.id)
        documents.append({
            "id": doc.id,
            "title": doc.metadata.get("title", "Без названия") if doc.metadata else "Без названия",
            "source": doc.metadata.get("source", "—") if doc.metadata else "—",
            "created_at": doc.created_at,
            "stats": stats,
            "has_pending": stats["pending"] > 0,
        })

    return render_template(
        "documents.html",
        documents=documents,
        core_available=core is not None,
    )


@ingest_bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
def delete_document(doc_id: int):
    """Удалить документ и все его чанки.

    HTMX endpoint — возвращает пустой ответ для удаления строки.
    """
    core = current_app.extensions.get("semantic_core")
    if not core:
        return jsonify({"error": "Core недоступен"}), 500

    try:
        deleted = core.delete(doc_id)
        logger.info(f"🗑️ Удалён документ {doc_id}, {deleted} записей")
        
        # Для HTMX — пустой ответ удаляет элемент
        if request.headers.get("HX-Request"):
            return "", 200
        
        flash(f"Документ удалён ({deleted} записей)", "success")
        return redirect(url_for("ingest.documents_page"))

    except Exception as e:
        logger.error(f"🔥 Ошибка удаления документа {doc_id}: {e}")
        if request.headers.get("HX-Request"):
            return jsonify({"error": str(e)}), 500
        flash(f"Ошибка удаления: {e}", "danger")
        return redirect(url_for("ingest.documents_page"))


@ingest_bp.route("/documents/<int:doc_id>/reindex", methods=["POST"])
def reindex_document(doc_id: int):
    """Переиндексировать документ.

    Удаляет старые чанки и создаёт новые.
    """
    core = current_app.extensions.get("semantic_core")
    if not core:
        flash("Core недоступен", "danger")
        return redirect(url_for("ingest.documents_page"))

    try:
        # Получаем документ
        doc_model = DocumentModel.get_or_none(DocumentModel.id == doc_id)
        if not doc_model:
            flash("Документ не найден", "warning")
            return redirect(url_for("ingest.documents_page"))

        # Получаем путь к файлу
        source = doc_model.metadata.get("source") if doc_model.metadata else None
        if not source or not Path(source).exists():
            flash("Исходный файл не найден", "warning")
            return redirect(url_for("ingest.documents_page"))

        # Читаем содержимое
        content = Path(source).read_text(encoding="utf-8")

        # Удаляем старый документ
        core.delete(doc_id)

        # Создаём новый
        doc = Document(
            content=content,
            metadata=doc_model.metadata or {},
        )
        core.ingest(doc)

        flash("Документ переиндексирован", "success")

    except Exception as e:
        logger.error(f"🔥 Ошибка переиндексации {doc_id}: {e}")
        flash(f"Ошибка: {e}", "danger")

    return redirect(url_for("ingest.documents_page"))
