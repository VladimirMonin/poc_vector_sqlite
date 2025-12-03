"""Утилиты для обработки медиа-файлов.

Модули:
    files: Валидация MIME-типов.
    tokens: Расчёт токенов для изображений.
    images: Оптимизация изображений.
    audio: Утилиты для работы с аудио (Phase 6.2).
    video: Утилиты для работы с видео (Phase 6.2).
"""

from semantic_core.infrastructure.media.utils.files import (
    SUPPORTED_IMAGE_MIME_TYPES,
    get_file_mime_type,
    is_image_valid,
    get_media_type,
)
from semantic_core.infrastructure.media.utils.tokens import (
    calculate_image_tokens,
    calculate_images_tokens,
    estimate_cost,
)
from semantic_core.infrastructure.media.utils.images import (
    resize_image,
    optimize_for_api,
)
from semantic_core.infrastructure.media.utils.audio import (
    DependencyError,
    ensure_ffmpeg,
    extract_audio_from_video,
    optimize_audio,
    optimize_audio_to_bytes,
    get_audio_duration,
    is_audio_supported,
    SUPPORTED_AUDIO_TYPES,
)
from semantic_core.infrastructure.media.utils.video import (
    extract_frames,
    frames_to_bytes,
    get_video_duration,
    get_video_metadata,
    is_video_supported,
    SUPPORTED_VIDEO_TYPES,
    QUALITY_PRESETS,
)

__all__ = [
    # files
    "SUPPORTED_IMAGE_MIME_TYPES",
    "get_file_mime_type",
    "is_image_valid",
    "get_media_type",
    # tokens
    "calculate_image_tokens",
    "calculate_images_tokens",
    "estimate_cost",
    # images
    "resize_image",
    "optimize_for_api",
    # audio (Phase 6.2)
    "DependencyError",
    "ensure_ffmpeg",
    "extract_audio_from_video",
    "optimize_audio",
    "optimize_audio_to_bytes",
    "get_audio_duration",
    "is_audio_supported",
    "SUPPORTED_AUDIO_TYPES",
    # video (Phase 6.2)
    "extract_frames",
    "frames_to_bytes",
    "get_video_duration",
    "get_video_metadata",
    "is_video_supported",
    "SUPPORTED_VIDEO_TYPES",
    "QUALITY_PRESETS",
]
