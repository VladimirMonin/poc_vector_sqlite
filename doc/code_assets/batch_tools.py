"""Batch and queue MCP tools for async task management.

This module provides MCP tools for:
- batch_generate_images: Create batch of image generation tasks
- queue_generate_audio: Create TTS task in local queue
- check_task_status: Check status of a single task
- check_batch_progress: Check progress of a batch

All constants (voices, aspect ratios, models) are imported from config.py.
Server is "dumb" - only validates and writes to DB.
Worker is "smart" - determines paths, calls APIs.
"""

import json
from pathlib import Path
from typing import List, Literal, Optional
from uuid import uuid4

from config import (
    GEMINI_VOICES_DATA,
    IMAGE_GEN_MODELS,
    TTS_MODELS,
    DEFAULT_TTS_MODEL,
    VALID_ASPECT_RATIOS,
    VALID_RESOLUTIONS,
)
from database import DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Получаем singleton instance базы данных
db = DatabaseManager()

# Извлекаем список валидных голосов из конфига (ключи словаря)
VALID_VOICES = list(GEMINI_VOICES_DATA.keys())


# ============================================================================
# Tool 1: batch_generate_images
# ============================================================================


def batch_generate_images(
    prompts: List[str],
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    model_type: Literal["fast", "pro"] = "fast",
) -> dict:
    """
    Create a batch of image generation tasks for async processing.

    This tool creates multiple image generation tasks that will be processed
    by Google Batch API. Use this when you need to generate 2+ images.

    **Cost savings:** 50% cheaper than sync generation.
    **Processing time:** 2-5 minutes (async).

    Args:
        prompts: List of English prompts for image generation (2-100 items).
                 Each prompt should be detailed and descriptive.
        aspect_ratio: Image aspect ratio. Valid values:
                     '1:1', '3:4', '4:3', '9:16', '16:9',
                     '2:3', '3:2', '4:5', '5:4', '21:9'.
                     Default: '1:1'.
        resolution: Output resolution: '1K' or '2K'.
                   Note: '2K' only works with model_type='pro'.
                   Default: '1K'.
        model_type: Generation model:
                   - 'fast': Gemini 2.5 Flash (quick, cheaper)
                   - 'pro': Gemini 3 Pro (higher quality, 2K support)
                   Default: 'fast'.

    Returns:
        dict: {
            "batch_id": "uuid",
            "total_tasks": 10,
            "status": "PENDING",
            "estimated_cost": "$0.025",
            "estimated_time": "2-5 minutes",
            "message": "Batch created. Use check_batch_progress(batch_id) to track."
        }

    Raises:
        ValueError: If prompts count is invalid (must be 2-100).
        ValueError: If aspect_ratio is not in valid list.
        ValueError: If resolution is invalid.
        ValueError: If model_type is invalid.

    Example:
        >>> result = await batch_generate_images(
        ...     prompts=["A red sports car", "A blue motorcycle"],
        ...     aspect_ratio="16:9",
        ...     model_type="fast"
        ... )
        >>> print(result["batch_id"])
        "550e8400-e29b-41d4-a716-446655440000"
    """
    # --- 1. Validation ---
    if not prompts or not (2 <= len(prompts) <= 100):
        raise ValueError(
            f"prompts must contain 2-100 items, got {len(prompts) if prompts else 0}"
        )

    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise ValueError(
            f"Invalid aspect_ratio '{aspect_ratio}'. "
            f"Valid options: {VALID_ASPECT_RATIOS}"
        )

    if resolution not in VALID_RESOLUTIONS:
        raise ValueError(
            f"Invalid resolution '{resolution}'. Valid options: {VALID_RESOLUTIONS}"
        )

    if model_type not in IMAGE_GEN_MODELS:
        raise ValueError(
            f"Invalid model_type '{model_type}'. "
            f"Valid options: {list(IMAGE_GEN_MODELS.keys())}"
        )

    # Fast model only supports 1K
    if model_type == "fast" and resolution == "2K":
        logger.warning("model_type='fast' only supports 1K. Forcing resolution='1K'.")
        resolution = "1K"

    # --- 2. Create batch_id ---
    batch_id = str(uuid4())
    logger.info(f"Creating batch {batch_id} with {len(prompts)} tasks")

    # --- 3. Prepare tasks ---
    # NOTE: target_path is None - worker will determine paths
    # Worker uses: media/generated/{batch_id}/{task_id}.png
    tasks = []
    for prompt in prompts:
        task_id = str(uuid4())
        tasks.append(
            {
                "task_id": task_id,
                "input_payload": json.dumps(
                    {
                        "prompt": prompt,
                        "aspect_ratio": aspect_ratio,
                        "resolution": resolution,
                        "model_type": model_type,
                    }
                ),
                "target_path": None,  # Worker decides the path
            }
        )

    # --- 4. Write to DB ---
    db.create_batch_with_tasks(
        batch_id=batch_id,
        operation_type="IMG_GEN_BATCH",
        tasks=tasks,
    )
    logger.info(f"Batch {batch_id} saved to DB with {len(tasks)} tasks")

    # --- 5. Calculate estimated cost ---
    # Batch API is 50% cheaper: ~$0.0025 per image
    cost_per_image = 0.0025
    estimated_cost = len(prompts) * cost_per_image

    # --- 6. Return result ---
    return {
        "batch_id": batch_id,
        "total_tasks": len(prompts),
        "status": "PENDING",
        "estimated_cost": f"${estimated_cost:.4f}",
        "estimated_time": "2-5 minutes",
        "message": (
            f"Batch created with {len(prompts)} image tasks. "
            f"Use check_batch_progress('{batch_id}') to track progress."
        ),
    }


# ============================================================================
# Tool 2: queue_generate_audio
# ============================================================================


def queue_generate_audio(
    text: str,
    voice: str = "puck",
    model_type: Literal["flash", "pro"] = "flash",
) -> dict:
    """
    Create a TTS (Text-to-Speech) task for async audio generation.

    This tool creates a single TTS task that will be processed by the
    local queue worker with rate limiting (respects API limits).

    **Processing time:** 5-10 seconds (includes rate limiting delay).

    Args:
        text: Text to synthesize (max 5000 characters).
              Should be clean text without special formatting.
        voice: Voice name for synthesis. Valid voices include:
               'puck' (Male, clear), 'kore' (Female, energetic),
               'charon' (Male, smooth), 'aoede' (Female, conversational),
               'fenrir' (Male, friendly), and many more.
               Default: 'puck'.
        model_type: TTS model:
                   - 'flash': Faster, cheaper (gemini-2.5-flash-preview-tts)
                   - 'pro': Higher quality (gemini-2.5-pro-preview-tts)
                   Default: 'flash'.

    Returns:
        dict: {
            "task_id": "uuid",
            "status": "PENDING",
            "estimated_cost": "$0.01",
            "estimated_time": "5-10 seconds",
            "message": "Task created. Use check_task_status(task_id) to track."
        }

    Raises:
        ValueError: If text is too long (>5000 characters).
        ValueError: If voice is not in valid list.
        ValueError: If model_type is invalid.

    Example:
        >>> result = await queue_generate_audio(
        ...     text="Hello, world! This is a test.",
        ...     voice="puck",
        ...     model_type="flash"
        ... )
        >>> print(result["task_id"])
        "550e8400-e29b-41d4-a716-446655440000"
    """
    # --- 1. Validation ---
    if not text or not text.strip():
        raise ValueError("text cannot be empty")

    if len(text) > 5000:
        raise ValueError(
            f"Text too long: {len(text)} characters. Maximum: 5000 characters."
        )

    # Normalize voice name to lowercase for comparison
    voice_lower = voice.lower()
    if voice_lower not in VALID_VOICES:
        # Show first 10 voices as example
        example_voices = VALID_VOICES[:10]
        raise ValueError(
            f"Invalid voice '{voice}'. "
            f"Examples: {example_voices}. "
            f"Total {len(VALID_VOICES)} voices available."
        )

    if model_type not in TTS_MODELS:
        raise ValueError(
            f"Invalid model_type '{model_type}'. "
            f"Valid options: {list(TTS_MODELS.keys())}"
        )

    # --- 2. Create IDs ---
    task_id = str(uuid4())
    batch_id = str(uuid4())  # TTS нужна batch-обёртка (FK constraint)
    logger.info(f"Creating TTS task {task_id} in batch {batch_id}")

    # --- 3. Get model name from config ---
    model_name = TTS_MODELS[model_type]

    # --- 4. Write to DB ---
    # TTS задачи создаются как batch с одной задачей
    # (схема требует batch_id из-за FK constraint)
    # Worker использует: media/tts/{task_id}.wav
    tasks = [
        {
            "task_id": task_id,
            "input_payload": json.dumps(
                {
                    "text": text,
                    "voice": voice_lower,
                    "model": model_name,
                    "model_type": model_type,
                }
            ),
            "target_path": None,  # Worker decides the path
        }
    ]

    db.create_batch_with_tasks(
        batch_id=batch_id,
        operation_type="TTS_GEN_QUEUE",
        tasks=tasks,
    )
    logger.info(f"TTS task {task_id} saved to DB (batch wrapper: {batch_id})")

    # --- 5. Calculate estimated cost ---
    estimated_cost = 0.01  # ~$0.01 per TTS request

    # --- 6. Return result ---
    return {
        "task_id": task_id,
        "status": "PENDING",
        "voice": voice_lower,
        "model": model_name,
        "estimated_cost": f"${estimated_cost:.2f}",
        "estimated_time": "5-10 seconds",
        "message": (
            f"TTS task created. Use check_task_status('{task_id}') to track progress."
        ),
    }


# ============================================================================
# Tool 3: check_task_status
# ============================================================================


def check_task_status(task_id: str) -> dict:
    """
    Check the status of a single task.

    Use this tool to track progress of tasks created by:
    - queue_generate_audio (TTS tasks)
    - Individual tasks from batch_generate_images

    Args:
        task_id: Task UUID returned by queue_generate_audio or from batch tasks.

    Returns:
        dict: {
            "task_id": "uuid",
            "operation_type": "TTS_GEN_QUEUE",
            "status": "COMPLETED",  # PENDING, PROCESSING, COMPLETED, FAILED
            "local_path": "/absolute/path/to/file.wav",  # If COMPLETED
            "error": "Error message",  # If FAILED
            "created_at": "2025-11-27 10:00:00",
            "completed_at": "2025-11-27 10:00:05"  # If COMPLETED
        }

    Raises:
        ValueError: If task_id is not found.

    Example:
        >>> result = await check_task_status("550e8400-e29b-41d4-a716-446655440000")
        >>> if result["status"] == "COMPLETED":
        ...     print(f"File saved at: {result['local_path']}")
    """
    # --- 1. Get task from DB ---
    task = db.get_task(task_id)

    if not task:
        raise ValueError(f"Task not found: {task_id}")

    # --- 2. Build response ---
    response = {
        "task_id": task["id"],
        "operation_type": task["operation_type"],
        "status": task["status"],
        "created_at": task["created_at"],
    }

    # Add local_path if completed (resolve to absolute)
    if task.get("local_path"):
        abs_path = str(Path(task["local_path"]).resolve())
        response["local_path"] = abs_path

    # Add error if failed
    if task.get("error_details"):
        response["error"] = task["error_details"]

    # Add completed_at if available
    if task.get("completed_at"):
        response["completed_at"] = task["completed_at"]

    return response


# ============================================================================
# Tool 4: check_batch_progress
# ============================================================================


def check_batch_progress(batch_id: str) -> dict:
    """
    Check the progress of a batch of tasks.

    Use this tool to track progress of batches created by batch_generate_images.

    Args:
        batch_id: Batch UUID returned by batch_generate_images.

    Returns:
        dict: {
            "batch_id": "uuid",
            "operation_type": "IMG_GEN_BATCH",
            "status": "PROCESSING",  # PENDING, SUBMITTED, PROCESSING, COMPLETED, FAILED
            "total_tasks": 10,
            "completed_tasks": 3,
            "failed_tasks": 0,
            "pending_tasks": 7,
            "progress_percent": 30,
            "google_batch_id": "batches/abc123",  # If submitted to Google
            "created_at": "2025-11-27 10:00:00",
            "completed_at": "2025-11-27 10:05:00",  # If completed
            "message": "Batch is being processed by Google Batch API"
        }

    Raises:
        ValueError: If batch_id is not found.

    Example:
        >>> result = await check_batch_progress("550e8400-e29b-41d4-a716-446655440000")
        >>> print(f"Progress: {result['progress_percent']}%")
        >>> if result["status"] == "COMPLETED":
        ...     print("All images generated!")
    """
    # --- 1. Get batch from DB ---
    batch = db.get_batch(batch_id)

    if not batch:
        raise ValueError(f"Batch not found: {batch_id}")

    # --- 2. Get progress statistics ---
    stats = db.get_batch_progress(batch_id)

    total = stats["total"]
    completed = stats["completed"]
    failed = stats["failed"]
    pending = stats["pending"]

    # Calculate progress percentage
    progress_percent = int((completed + failed) / total * 100) if total > 0 else 0

    # --- 3. Generate status message ---
    status = batch["status"]
    if status == "PENDING":
        message = "Batch is waiting to be submitted to Google Batch API"
    elif status == "SUBMITTED":
        message = "Batch has been submitted to Google Batch API"
    elif status == "PROCESSING":
        message = f"Batch is being processed: {completed}/{total} tasks completed"
    elif status == "COMPLETED":
        message = f"Batch completed: {completed} succeeded, {failed} failed"
    elif status == "FAILED":
        message = f"Batch failed: {failed} tasks failed"
    else:
        message = f"Batch status: {status}"

    # --- 4. Build response ---
    response = {
        "batch_id": batch["id"],
        "operation_type": batch["operation_type"],
        "status": status,
        "total_tasks": total,
        "completed_tasks": completed,
        "failed_tasks": failed,
        "pending_tasks": pending,
        "progress_percent": progress_percent,
        "created_at": batch["created_at"],
        "message": message,
    }

    # Add google_batch_id if available
    if batch.get("google_batch_id"):
        response["google_batch_id"] = batch["google_batch_id"]

    # Add completed_at if available
    if batch.get("completed_at"):
        response["completed_at"] = batch["completed_at"]

    return response
