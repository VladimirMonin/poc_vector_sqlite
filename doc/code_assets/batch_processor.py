"""Обработчик пакетных задач через Google Batch API.

Функции:
    submit_pending_batches(db) -> int
        Отправляет PENDING задачи в Google Batch API.
    poll_active_batches(db) -> int
        Проверяет статусы активных пакетов.
    retrieve_completed_batches(db) -> int
        Скачивает результаты завершённых пакетов.
"""

import base64
import json
import logging
import os
import tempfile
from pathlib import Path

import google.genai as genai
from google.genai import types

from config import GEMINI_API_KEY, get_batch_model

logger = logging.getLogger("gemini-media-mcp.worker.batch_processor")

ENABLE_BATCH_API = os.getenv("ENABLE_BATCH_API", "true").lower() == "true"

client = None
if ENABLE_BATCH_API:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("✅ Google Batch API client инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Google Batch API client: {e}")
        logger.warning("⚠️ Переключение в MOCK режим")
        ENABLE_BATCH_API = False
        client = None
else:
    logger.info("ℹ️ ENABLE_BATCH_API=false → MOCK режим")


def submit_pending_batches(db) -> int:
    """Отправляет PENDING задачи в Google Batch API.

    Args:
        db: DatabaseManager instance.

    Returns:
        Количество отправленных пакетов.
    """
    pending_batches = db.get_pending_batches()

    batch_mode_batches = []
    for batch in pending_batches:
        all_batch_tasks = db.get_tasks_by_batch(batch["id"])
        tasks_in_batch = [t for t in all_batch_tasks if t.get("status") == "PENDING"]

        if not tasks_in_batch:
            logger.warning(f"⚠️ Batch {batch['id']} не имеет PENDING задач, пропуск")
            continue

        first_task = tasks_in_batch[0]
        op_type = db.get_operation_type(first_task["operation_type"])

        if op_type["execution_mode"] == "batch":
            batch_mode_batches.append({"batch": batch, "tasks": tasks_in_batch})

    submitted_count = 0

    for item in batch_mode_batches:
        batch = item["batch"]
        tasks = item["tasks"]
        batch_id = batch["id"]

        logger.info(f"🚀 Отправка batch {batch_id} с {len(tasks)} задачами")

        try:
            if not ENABLE_BATCH_API:
                fake_google_id = f"batches/mock_{batch_id[:8]}"
                logger.info(f"🧪 [MOCK] Создан batch: {fake_google_id}")

                db.update_batch_status(batch_id, "SUBMITTED", fake_google_id)

                for task in tasks:
                    db.update_task_status(task["id"], "SUBMITTED")

                submitted_count += 1
            else:
                tasks.sort(key=lambda t: (t["created_at"], t["id"]))

                jsonl_lines = []
                for task in tasks:
                    input_payload = task.get("input_payload", {})

                    if isinstance(input_payload, str):
                        input_payload = json.loads(input_payload)

                    prompt = input_payload.get("prompt", "")

                    request_obj = {
                        "key": task["id"],
                        "request": {
                            "contents": [{"parts": [{"text": prompt}], "role": "user"}],
                            "generation_config": {
                                "responseModalities": ["TEXT", "IMAGE"]
                            },
                        },
                    }
                    jsonl_lines.append(json.dumps(request_obj))

                # Записать JSONL во временный файл и загрузить в File API
                jsonl_content = "\n".join(jsonl_lines)

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
                ) as f:
                    f.write(jsonl_content)
                    temp_file_path = f.name

                try:
                    # Загрузить файл в Google File API
                    uploaded_file = client.files.upload(
                        file=temp_file_path,
                        config=types.UploadFileConfig(
                            display_name=f"batch-{batch_id[:8]}",
                            mime_type="application/jsonl",
                        ),
                    )
                    logger.info(f"📤 Uploaded JSONL: {uploaded_file.name}")

                    # Динамически выбираем модель по operation_type
                    operation_type = tasks[0]["operation_type"]
                    first_payload = tasks[0].get("input_payload", {})
                    if isinstance(first_payload, str):
                        first_payload = json.loads(first_payload)
                    model = get_batch_model(operation_type, first_payload)

                    logger.info(
                        f"Selected model: {model} (operation: {operation_type})"
                    )

                    # Вызываем Batch API с file-based source
                    result = client.batches.create(
                        model=model,
                        src=uploaded_file.name,
                        config={"display_name": f"batch-{batch_id[:8]}"},
                    )

                    google_batch_id = result.name  # "batches/abc123xyz..."
                    logger.info(f"Batch submitted: {google_batch_id}")

                    # Удалить входной JSONL файл из Google Cloud
                    # (файлы хранятся 48ч и занимают квоту 20GB на проект)
                    try:
                        client.files.delete(name=uploaded_file.name)
                        logger.debug(f"Deleted input file: {uploaded_file.name}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete input file {uploaded_file.name}: {e}"
                        )

                    # Обновить статус пакета
                    db.update_batch_status(batch_id, "SUBMITTED", google_batch_id)

                    # Обновить статусы всех задач в пакете
                    for task in tasks:
                        db.update_task_status(task["id"], "SUBMITTED")

                    submitted_count += 1

                finally:
                    # Удалить временный файл
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"❌ Failed to submit batch {batch_id}: {e}")
            # Пометить пакет как FAILED (error message залогирован выше)
            db.update_batch_status(batch_id, "FAILED")

    logger.info(f"Submitted {submitted_count}/{len(batch_mode_batches)} batches")
    return submitted_count


def poll_active_batches(db) -> int:
    """Проверяет статусы активных пакетов в Google Batch API.

    Args:
        db: DatabaseManager instance.

    Returns:
        Количество обработанных пакетов.
    """
    batches = db.get_pending_batches()
    active_batches = [
        b
        for b in batches
        if b.get("google_batch_id") and b["status"] in ["SUBMITTED", "PROCESSING"]
    ]

    if not active_batches:
        return 0

    logger.info(f"📊 Проверка {len(active_batches)} активных пакетов")

    STATUS_MAP = {
        "JOB_STATE_PENDING": "SUBMITTED",
        "JOB_STATE_RUNNING": "PROCESSING",
        "JOB_STATE_SUCCEEDED": "COMPLETED",
        "JOB_STATE_FAILED": "FAILED",
        "JOB_STATE_CANCELLED": "FAILED",
        "STATE_UNSPECIFIED": "SUBMITTED",
    }

    processed_count = 0

    for batch in active_batches:
        batch_id = batch["id"]
        google_batch_id = batch["google_batch_id"]
        current_status = batch["status"]

        try:
            # 3. Определить новый статус
            new_status = None

            # КРИТИЧЕСКАЯ ПРОВЕРКА: Mock ID (из Step 1)
            if google_batch_id.startswith("batches/mock_"):
                # Mock режим: эмулируем быстрое завершение для тестов
                if not ENABLE_BATCH_API:
                    # Переход: SUBMITTED → PROCESSING → COMPLETED
                    if current_status == "SUBMITTED":
                        new_status = "PROCESSING"
                    elif current_status == "PROCESSING":
                        new_status = "COMPLETED"

                    logger.debug(
                        f"🧪 [MOCK] Batch {batch_id[:8]} emulated: {current_status} → {new_status}"
                    )
                else:
                    # Если ENABLE_BATCH_API=true, но ID mock → пропустить
                    logger.warning(
                        f"⚠️ Batch {batch_id[:8]} has mock ID but ENABLE_BATCH_API=true. "
                        f"Skipping (inconsistent state)"
                    )
                    continue

            # Real API режим
            elif ENABLE_BATCH_API and client:
                # Запрос к Google Batch API
                google_batch = client.batches.get(name=google_batch_id)

                # Получить статус (например: "JOB_STATE_RUNNING")
                google_state = google_batch.state

                # Преобразовать в наш статус
                new_status = STATUS_MAP.get(google_state, "SUBMITTED")

                logger.debug(
                    f"📡 Batch {batch_id[:8]}: Google state={google_state} → DB status={new_status}"
                )

            else:
                # ENABLE_BATCH_API=false и не mock ID → пропустить
                logger.warning(
                    f"⚠️ Batch {batch_id[:8]} has real ID but ENABLE_BATCH_API=false. "
                    f"Cannot poll without API access"
                )
                continue

            # 4. Обновить БД только если статус изменился (оптимизация)
            if new_status and new_status != current_status:
                db.update_batch_status(batch_id, new_status)
                logger.info(
                    f"✅ Batch {batch_id[:8]} status updated: {current_status} → {new_status}"
                )
            elif new_status == current_status:
                logger.debug(
                    f"⏸️ Batch {batch_id[:8]} status unchanged: {current_status}"
                )

            processed_count += 1

        except Exception as e:
            # Обработка ошибок: 404, rate limits, network issues
            logger.error(f"❌ Failed to poll batch {batch_id[:8]}: {e}")

            # НЕ обновляем статус на FAILED при ошибке polling
            # Это может быть временная проблема (сеть, rate limit)
            # Повторим проверку в следующем цикле

            # Однако если это 404 NOT_FOUND, можно пометить как FAILED
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                logger.warning(
                    f"⚠️ Batch {batch_id[:8]} not found in Google API. "
                    f"Possible causes: expired, deleted, or invalid ID"
                )
                # Опционально: можно пометить как FAILED после N попыток
                # Но для MVP оставляем в текущем статусе для retry

    logger.info(
        f"📊 Polling complete: {processed_count}/{len(active_batches)} batches processed"
    )
    return processed_count


def retrieve_completed_batches(db) -> int:
    """Скачивает и обрабатывает результаты COMPLETED пакетов.

    Args:
        db: DatabaseManager instance.

    Returns:
        Количество обработанных батчей.
    """
    all_batches = db.get_pending_batches()

    try:
        completed_status_batches = db._batches.get_by_status("COMPLETED")
        all_batches.extend(completed_status_batches)
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запросить COMPLETED батчи: {e}")

    completed_batches = [
        b
        for b in all_batches
        if b["status"] == "COMPLETED" and b.get("google_batch_id")
    ]

    if not completed_batches:
        return 0

    logger.info(
        f"📥 Загрузка результатов из {len(completed_batches)} завершённых пакетов"
    )

    processed_count = 0

    for batch in completed_batches:
        batch_id = batch["id"]
        google_batch_id = batch["google_batch_id"]

        try:
            # 2. Mock режим: эмулировать успешные результаты
            if google_batch_id.startswith("batches/mock_"):
                if not ENABLE_BATCH_API:
                    # Получить задачи батча в детерминированном порядке
                    tasks = db.get_tasks_by_batch(batch_id)
                    tasks.sort(key=lambda t: (t["created_at"], t["id"]))

                    logger.info(
                        f"🧪 [MOCK] Processing batch {batch_id[:8]} with {len(tasks)} tasks"
                    )

                    # Эмулировать успешные результаты для всех задач
                    for task in tasks:
                        # Mock: создать фейковое изображение (1x1 прозрачный PNG)
                        mock_png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

                        # Сохранить с шардингом
                        local_path = _save_image(
                            batch_id,
                            task["id"],
                            mock_png_base64,
                            task.get("target_path"),
                        )

                        # Обновить БД
                        db.update_task_completed(task["id"], local_path=local_path)
                        logger.debug(
                            f"✅ [MOCK] Task {task['id'][:8]} completed: {local_path}"
                        )

                    # Закрыть батч
                    db.update_batch_completed(batch_id)
                    logger.info(f"✅ [MOCK] Batch {batch_id[:8]} completed")
                    processed_count += 1
                    continue
                else:
                    # Режим для тестов: mock ID но ENABLE_BATCH_API=true
                    # Используем Real API path с mock client (патченный в тестах)
                    pass  # Продолжаем вниз к Real API режиму

            # 3. Real API режим (file-based)
            if not ENABLE_BATCH_API or not client:
                logger.warning(
                    f"Batch {batch_id[:8]} has real ID but ENABLE_BATCH_API=false"
                )
                continue

            # Получить объект батча из Google
            google_batch = client.batches.get(name=google_batch_id)

            # Проверить статус батча (state может быть enum или string)
            batch_state = google_batch.state
            batch_state_str = str(batch_state)
            if "SUCCEEDED" not in batch_state_str:
                logger.warning(
                    f"Batch {batch_id[:8]} not ready yet. State: {batch_state}"
                )
                continue

            # File-based режим: результаты в dest.file_name (JSONL файл)
            dest = getattr(google_batch, "dest", None)
            if dest is None:
                logger.error(
                    f"Batch {batch_id[:8]} has no dest attribute. Cannot retrieve results."
                )
                continue

            output_file = getattr(dest, "file_name", None)
            if not output_file:
                # Попробуем inlined_responses как fallback
                inlined = getattr(dest, "inlined_responses", None)
                if inlined:
                    logger.warning(
                        f"Batch {batch_id[:8]} has inlined_responses but we expected file_name. "
                        f"This shouldn't happen with file-based submission."
                    )
                logger.error(
                    f"Batch {batch_id[:8]} has no file_name in dest. Attrs: {dir(dest)}"
                )
                continue

            logger.info(f"Downloading results from: {output_file}")

            # Скачать JSONL файл через Files API
            try:
                file_content_bytes = client.files.download(file=output_file)
                file_content = file_content_bytes.decode("utf-8")
            except Exception as e:
                logger.error(
                    f"Failed to download results file for batch {batch_id[:8]}: {e}"
                )
                continue

            # Парсить JSONL — каждая строка содержит {"key": "task_id", "response": {...}}
            # или {"key": "task_id", "error": {...}}
            results_by_key = {}
            for line in file_content.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                    key = parsed.get("key")
                    if key:
                        results_by_key[key] = parsed
                    else:
                        logger.warning(f"Result line without key: {line[:100]}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in result line: {e}")

            logger.info(
                f"Parsed {len(results_by_key)} results for batch {batch_id[:8]}"
            )

            # Получить задачи батча
            tasks = db.get_tasks_by_batch(batch_id)

            # Обработать каждую задачу по её key (task_id)
            success_count = 0
            fail_count = 0

            for task in tasks:
                task_id = task["id"]
                result = results_by_key.get(task_id)

                if not result:
                    logger.warning(f"No result found for task {task_id[:8]}")
                    db.update_task_failed(task_id, error="No result in batch response")
                    fail_count += 1
                    continue

                # Проверка на ошибку в результате
                if "error" in result:
                    error_msg = result["error"].get("message", str(result["error"]))
                    logger.warning(f"Task {task_id[:8]} failed: {error_msg}")
                    db.update_task_failed(task_id, error=error_msg)
                    fail_count += 1
                elif "response" in result:
                    # Успех: извлечь и сохранить изображение
                    try:
                        base64_data = _extract_image_data_from_dict(result["response"])
                        local_path = _save_image(
                            batch_id, task_id, base64_data, task.get("target_path")
                        )
                        db.update_task_completed(task_id, local_path=local_path)
                        logger.debug(f"Task {task_id[:8]} completed: {local_path}")
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to save task {task_id[:8]}: {e}")
                        db.update_task_failed(task_id, error=f"Save error: {e}")
                        fail_count += 1
                else:
                    logger.warning(f"Task {task_id[:8]} has no response or error")
                    db.update_task_failed(task_id, error="Empty result")
                    fail_count += 1

            # Закрыть батч
            db.update_batch_completed(batch_id)
            logger.info(
                f"Batch {batch_id[:8]} completed: {success_count} success, {fail_count} failed"
            )
            processed_count += 1

        except Exception as e:
            logger.error(f"Failed to retrieve batch {batch_id[:8]}: {e}")
            # НЕ помечаем как FAILED при ошибке скачивания (может быть transient)
            # Повторим в следующем цикле

    logger.info(
        f"Retrieval complete: {processed_count}/{len(completed_batches)} batches processed"
    )
    return processed_count


def _extract_image_data_from_dict(response: dict) -> str:
    """Извлекает base64 данные изображения из ответа Google Batch API.

    Args:
        response: Dict с ответом из JSONL файла.

    Returns:
        Base64 строка.

    Raises:
        ValueError: Если нет данных изображения в ответе.
    """
    try:
        candidate = response["candidates"][0]
        parts = candidate["content"]["parts"]

        for part in parts:
            inline_data = part.get("inlineData") or part.get("inline_data")
            if inline_data:
                data = inline_data.get("data")
                if data:
                    return data

        raise ValueError("No image data found in any part")

    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Failed to extract image data from response: {e}")


def _save_image(
    batch_id: str, task_id: str, base64_data: str, target_path: str = None
) -> str:
    """Сохраняет изображение из base64 с файловым шардингом.

    Args:
        batch_id: UUID батча.
        task_id: UUID задачи.
        base64_data: Base64 строка изображения.
        target_path: Путь из задачи.

    Returns:
        Абсолютный путь к сохранённому файлу.

    Raises:
        IOError: Если не удалось сохранить файл.
    """
    image_bytes = base64.b64decode(base64_data)
    if target_path:
        try:
            local_path = Path(target_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, "wb") as f:
                f.write(image_bytes)

            logger.debug(f"💾 Сохранено в target_path: {local_path}")
            return str(local_path.absolute())
        except (IOError, OSError) as e:
            logger.warning(
                f"⚠️ Не удалось сохранить в {target_path}: {e}. Использую fallback."
            )

    output_dir = Path("media") / "generated" / batch_id
    output_dir.mkdir(parents=True, exist_ok=True)

    local_path = output_dir / f"{task_id}.png"

    with open(local_path, "wb") as f:
        f.write(image_bytes)

    logger.debug(f"💾 Сохранено в fallback: {local_path}")
    return str(local_path.absolute())
