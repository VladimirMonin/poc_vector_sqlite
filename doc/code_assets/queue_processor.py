"""
Queue Processor — обработка задач в режиме local_queue (последовательная обработка).

Используется для операций, которые НЕ поддерживают Google Batch API
(например, TTS из-за бага Google — Batch TTS возвращает 404 NOT_FOUND).

Архитектурные решения:
- rpm_limit читается динамически из operation_types (не хардкод)
- Модели TTS берутся из config.TTS_MODELS (не хардкод)
- Файлы сохраняются в media/tts/{task_id}.wav (единообразие с media/generated/)
"""

import logging
import time
import wave
from pathlib import Path
from typing import Optional

from google import genai

import config

logger = logging.getLogger("gemini-media-mcp.worker.queue_processor")


# ============================================================================
# Rate Limiting (динамическое из БД)
# ============================================================================


def _get_rate_limit_delay(db, operation_type: str) -> float:
    """
    Вычислить задержку между запросами из rpm_limit в operation_types.

    Args:
        db: DatabaseManager instance
        operation_type: Код операции (например, 'TTS_GEN_QUEUE')

    Returns:
        Задержка в секундах = 60 / rpm_limit
        Дефолт: 20 секунд (3 RPM для Free Tier) если rpm_limit не указан
    """
    op_type = db.get_operation_type(operation_type)

    if op_type is None:
        logger.warning(
            f"Operation type {operation_type} not found, using default delay"
        )
        return 20.0  # 3 RPM fallback

    rpm_limit = op_type.get("rpm_limit")

    if rpm_limit is None or rpm_limit <= 0:
        logger.warning(f"Invalid rpm_limit for {operation_type}, using default delay")
        return 20.0  # 3 RPM fallback

    delay = 60.0 / rpm_limit
    logger.debug(
        f"Rate limit for {operation_type}: {rpm_limit} RPM → {delay:.1f}s delay"
    )

    return delay


# ============================================================================
# Audio File Saving (структура media/tts/)
# ============================================================================


def _save_tts_audio(
    task_id: str, pcm_data: bytes, target_path: Optional[str] = None
) -> str:
    """
    Сохранить TTS аудио в WAV файл.

    Gemini TTS API возвращает RAW PCM данные (не готовый WAV!).
    Параметры PCM: 24000 Hz, 16-bit, mono (из документации Google).

    Args:
        task_id: UUID задачи
        pcm_data: RAW PCM bytes от Gemini TTS API (inline_data.data)
        target_path: Явный путь из задачи (если указан пользователем)

    Returns:
        Абсолютный путь к сохранённому WAV файлу

    Note:
        Если target_path не указан, используется media/tts/{task_id}.wav
    """
    if target_path:
        local_path = Path(target_path)
    else:
        local_path = Path(config.OUTPUT_TTS_DIR) / f"{task_id}.wav"

    # Создать директории
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Записать WAV файл с правильным заголовком
    # Параметры из документации Google TTS:
    # - channels: 1 (mono)
    # - sample_width: 2 (16-bit)
    # - framerate: 24000 Hz
    with wave.open(str(local_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)

    logger.debug(f"TTS audio saved: {local_path} ({len(pcm_data)} bytes PCM)")

    return str(local_path.absolute())


# ============================================================================
# TTS Generation (реальный вызов Gemini API)
# ============================================================================


def _generate_tts(text: str, voice: str, model_type: str) -> bytes:
    """
    Вызвать Gemini TTS API и вернуть аудио данные.

    Args:
        text: Текст для синтеза
        voice: Имя голоса (Puck, Kore, etc.)
        model_type: 'flash' или 'pro'

    Returns:
        Raw audio bytes от Gemini TTS API

    Raises:
        ValueError: Если API не вернул аудио данные
        RuntimeError: Если API вернул ошибку
    """
    # Получить имя модели из конфига
    model_name = config.TTS_MODELS.get(
        model_type, config.TTS_MODELS[config.DEFAULT_TTS_MODEL]
    )

    logger.debug(
        f"TTS API call: model={model_name}, voice={voice}, text_len={len(text)}"
    )

    # Инициализация клиента
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Вызов TTS API
    response = client.models.generate_content(
        model=model_name,
        contents=text,
        config={
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {"prebuilt_voice_config": {"voice_name": voice}}
            },
        },
    )

    # Извлечь аудио данные
    if not response.candidates:
        raise ValueError("TTS API returned no candidates")

    audio_part = response.candidates[0].content.parts[0]

    if not hasattr(audio_part, "inline_data"):
        raise ValueError("TTS API returned no audio data (missing inline_data)")

    return audio_part.inline_data.data


# ============================================================================
# Validation
# ============================================================================


def _validate_tts_payload(payload: dict) -> tuple[str, str, str]:
    """
    Валидировать input_payload TTS задачи.

    Args:
        payload: dict с text, voice, model_type

    Returns:
        Tuple (text, voice, model_type) с дефолтами

    Raises:
        ValueError: Если text пустой или слишком длинный
    """
    text = payload.get("text", "")
    voice = payload.get("voice", config.DEFAULT_VOICE)
    model_type = payload.get("model_type", config.DEFAULT_TTS_MODEL)

    # Валидация text
    if not text or not text.strip():
        raise ValueError("TTS text is empty")

    if len(text) > 5000:
        raise ValueError(f"TTS text too long: {len(text)} > 5000 characters")

    # Валидация voice (опционально — можно добавить проверку по GEMINI_VOICES_DATA)
    if voice.lower() not in config.GEMINI_VOICES_DATA:
        logger.warning(f"Voice '{voice}' not in known voices, proceeding anyway")

    # Валидация model_type
    if model_type not in config.TTS_MODELS:
        logger.warning(f"Unknown model_type '{model_type}', using default")
        model_type = config.DEFAULT_TTS_MODEL

    return text.strip(), voice.capitalize(), model_type


# ============================================================================
# Main Processor
# ============================================================================


def process_local_queue_tasks(db, *, mock_mode: bool = False) -> int:
    """
    Обработать 1 задачу из local_queue (последовательная обработка).

    Режим local_queue используется для операций БЕЗ поддержки Batch API:
    - TTS_GEN_QUEUE (Batch API возвращает 404 NOT_FOUND)

    Args:
        db: DatabaseManager instance
        mock_mode: Если True, не вызывать реальный API (для тестов)

    Returns:
        1 если задача обработана, 0 если очередь пуста

    Note:
        - Обрабатывает только 1 задачу за вызов
        - rate limiting применяется ПОСЛЕ успешной обработки
        - Задержка вычисляется динамически из rpm_limit в operation_types
    """
    # Получить 1 pending задачу с execution_mode='local_queue'
    tasks = db.get_pending_local_queue_tasks(limit=1)

    if not tasks:
        logger.debug("Local queue is empty")
        return 0

    task = tasks[0]
    task_id = task["id"]
    task_id_short = task_id[:8]
    operation_type = task["operation_type"]

    logger.info(f"Processing local_queue task {task_id_short} ({operation_type})")

    # Обновить статус на PROCESSING
    db.update_task_status(task_id, "PROCESSING")

    try:
        # Извлечь payload
        payload = task["input_payload"]
        if isinstance(payload, str):
            import json

            payload = json.loads(payload)

        # Валидация
        text, voice, model_type = _validate_tts_payload(payload)
        target_path = task.get("target_path")

        if mock_mode:
            # Тестовый режим — не вызываем реальный API
            logger.debug(f"[MOCK] TTS for task {task_id_short}: {text[:50]}...")
            result_path = target_path or str(
                Path(config.OUTPUT_TTS_DIR) / f"{task_id}.wav"
            )
        else:
            # Реальный вызов TTS API
            audio_pcm_data = _generate_tts(text, voice, model_type)

            # Сохранить аудио
            result_path = _save_tts_audio(task_id, audio_pcm_data, target_path)

        # Обновить статус на COMPLETED
        db.update_task_completed(task_id, result_path)
        logger.info(f"TTS task {task_id_short} completed: {result_path}")

        # Rate Limiting (динамически из БД)
        if not mock_mode:
            delay = _get_rate_limit_delay(db, operation_type)
            logger.debug(f"Rate limit sleep: {delay:.1f}s")
            time.sleep(delay)

        return 1

    except Exception as e:
        # Обработка ошибок
        error_msg = str(e)
        logger.error(f"TTS task {task_id_short} failed: {error_msg}")
        db.update_task_failed(task_id, error_msg)

        return 1  # Задача обработана (с ошибкой), продолжаем работу
