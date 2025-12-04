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
    запускает ingest() для документов и ingest_image() для медиа.

    Поддерживаемые типы:
        - Документы: .md, .markdown, .txt
        - Изображения: .png, .jpg, .jpeg, .gif, .webp
        - Аудио: .mp3, .wav, .ogg (будущее)
        - Видео: .mp4, .webm (будущее)

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
    text_files: list[Path] = []  # .md, .markdown, .txt
    image_files: list[Path] = []  # .png, .jpg, .jpeg, .gif, .webp
    errors: list[str] = []

    # Расширения по категориям
    TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    # Сохраняем все файлы
    for file in files:
        if file.filename:
            result = upload_service.save_file(file.stream, file.filename)
            if result.success:
                uploaded_files[result.original_name] = result.path
                ext = result.path.suffix.lower()
                if ext in TEXT_EXTENSIONS:
                    text_files.append(result.path)
                elif ext in IMAGE_EXTENSIONS:
                    image_files.append(result.path)
            else:
                errors.append(f"{result.original_name}: {result.error}")

    if errors:
        for error in errors:
            flash(error, "danger")

    # Определяем режим (sync/async)
    total_files = len(text_files) + len(image_files)
    mode = "async" if total_files >= ASYNC_THRESHOLD else "sync"
    logger.info(f"📤 Загружено {len(files)} файлов (text={len(text_files)}, images={len(image_files)}), mode={mode}")

    ingested_docs = 0
    ingested_images = 0

    # === Индексируем текстовые файлы (.md, .markdown, .txt) ===
    for text_path in text_files:
        try:
            # Для Markdown — обновляем пути к медиа
            if text_path.suffix.lower() in (".md", ".markdown"):
                content = upload_service.process_markdown_paths(
                    text_path,
                    {Path(name).name: path for name, path in uploaded_files.items()},
                )
            else:
                # Для .txt — просто читаем содержимое
                content = text_path.read_text(encoding="utf-8")

            # Создаём документ
            doc = Document(
                content=content,
                metadata={
                    "title": text_path.stem.replace("_", " ").title(),
                    "source": str(text_path),
                    "source_type": "upload",
                },
            )

            # Индексируем
            core.ingest(doc, mode=mode)
            ingested_docs += 1

        except Exception as e:
            logger.error(f"🔥 Ошибка индексации {text_path}: {e}")
            flash(f"Ошибка индексации {text_path.name}: {e}", "danger")

    # === Индексируем изображения через Vision API ===
    for image_path in image_files:
        try:
            # Проверяем, есть ли image_analyzer
            if core.image_analyzer is None:
                logger.warning(f"⚠️ ImageAnalyzer не настроен, пропускаем {image_path.name}")
                flash(f"⚠️ {image_path.name}: Vision API не настроен", "warning")
                continue

            # Используем Vision API для анализа изображения
            logger.info(f"🖼️ Анализируем изображение: {image_path.name}")
            core.ingest_image(str(image_path), mode=mode)
            ingested_images += 1

        except Exception as e:
            logger.error(f"🔥 Ошибка индексации изображения {image_path}: {e}")
            flash(f"Ошибка индексации {image_path.name}: {e}", "danger")

    # === Формируем сообщение ===
    total_ingested = ingested_docs + ingested_images
    if total_ingested > 0:
        parts = []
        if ingested_docs > 0:
            parts.append(f"{ingested_docs} документ(ов)")
        if ingested_images > 0:
            parts.append(f"{ingested_images} изображений")

        message = f"✅ Загружено и проиндексировано: {', '.join(parts)}"
        if mode == "async":
            message += " (обработка в фоне)"

        flash(message, "success")
    elif not errors:
        flash("Нет файлов для индексации", "warning")

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

        # metadata может быть dict или строкой (JSON) в зависимости от версии
        meta = doc.metadata
        if isinstance(meta, str):
            import json

            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}

        documents.append(
            {
                "id": doc.id,
                "title": meta.get("title", "Без названия")
                if isinstance(meta, dict)
                else "Без названия",
                "source": meta.get("source", "—") if isinstance(meta, dict) else "—",
                "created_at": doc.created_at,
                "stats": stats,
                "has_pending": stats["pending"] > 0,
            }
        )

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
