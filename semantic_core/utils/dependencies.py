"""Утилиты для проверки доступности optional dependencies.

Используется в ComponentFactory для graceful degradation
и в CLI для предупреждений пользователю.
"""

import platform
from typing import Dict, List, Optional


def _is_apple_silicon() -> bool:
    """Проверяет, запущено ли на Apple Silicon (M1/M2/M3/M4)."""
    return platform.machine() == "arm64" and platform.system() == "Darwin"


def check_google_available() -> tuple[bool, Optional[str]]:
    """Проверяет доступность Google SDK.

    Returns:
        (available, error_message): True если доступен, иначе (False, error).
    """
    try:
        import google.generativeai  # noqa
        import google.genai  # noqa

        return True, None
    except ImportError as e:
        return False, str(e)


def check_openai_available() -> tuple[bool, Optional[str]]:
    """Проверяет доступность OpenAI SDK.

    Returns:
        (available, error_message): True если доступен, иначе (False, error).
    """
    try:
        import openai  # noqa

        return True, None
    except ImportError as e:
        return False, str(e)


def check_local_embeddings_available() -> tuple[bool, Optional[str]]:
    """Проверяет доступность local embeddings.

    Returns:
        (available, error_message): True если доступен, иначе (False, error).
    """
    try:
        if _is_apple_silicon():
            import mlx  # noqa
            import mlx_embeddings  # noqa
        else:
            import sentence_transformers  # noqa
        return True, None
    except ImportError as e:
        return False, str(e)


def check_local_whisper_available() -> tuple[bool, Optional[str]]:
    """Проверяет доступность Whisper.

    Returns:
        (available, error_message): True если доступен, иначе (False, error).
    """
    try:
        if _is_apple_silicon():
            import lightning_whisper_mlx  # noqa
        else:
            import transformers  # noqa
        return True, None
    except ImportError as e:
        return False, str(e)


def check_media_available() -> tuple[bool, Optional[str]]:
    """Проверяет доступность media processing libs.

    Returns:
        (available, error_message): True если доступен, иначе (False, error).
    """
    try:
        import PIL  # noqa
        import pydub  # noqa
        import imageio  # noqa

        return True, None
    except ImportError as e:
        return False, str(e)


def get_available_providers() -> Dict[str, bool]:
    """Возвращает dict с доступностью всех провайдеров.

    Returns:
        Dict с ключами: google, openai, local_embeddings, local_whisper, media
    """
    return {
        "google": check_google_available()[0],
        "openai": check_openai_available()[0],
        "local_embeddings": check_local_embeddings_available()[0],
        "local_whisper": check_local_whisper_available()[0],
        "media": check_media_available()[0],
    }


def get_missing_providers() -> List[str]:
    """Возвращает список отсутствующих провайдеров.

    Returns:
        List имён провайдеров которые не установлены.
    """
    available = get_available_providers()
    return [name for name, is_available in available.items() if not is_available]


def get_install_hint(provider: str) -> str:
    """Возвращает hint для установки провайдера.

    Args:
        provider: Имя провайдера (google, openai, local_embeddings, etc).

    Returns:
        Строка с командой установки.
    """
    hints = {
        "google": "pip install poc-vector-sqlite[google]",
        "openai": "pip install poc-vector-sqlite[openai]",
        "local_embeddings": (
            "pip install poc-vector-sqlite[local-embeddings-mlx]"
            if _is_apple_silicon()
            else "pip install poc-vector-sqlite[local-embeddings]"
        ),
        "local_whisper": (
            "pip install poc-vector-sqlite[local-whisper-mlx]"
            if _is_apple_silicon()
            else "pip install poc-vector-sqlite[local-whisper]"
        ),
        "media": "pip install poc-vector-sqlite[media]",
    }
    return hints.get(provider, f"pip install poc-vector-sqlite[{provider}]")


def require_provider(provider: str, feature: str = "") -> None:
    """Проверяет наличие провайдера, иначе выбрасывает ImportError.

    Args:
        provider: Имя провайдера.
        feature: Название фичи для более понятного сообщения.

    Raises:
        ImportError: Если провайдер не установлен.

    Example:
        >>> require_provider("google", "Gemini embeddings")
        Traceback (most recent call last):
        ImportError: Google SDK not installed. Install with: pip install poc-vector-sqlite[google]
    """
    check_funcs = {
        "google": check_google_available,
        "openai": check_openai_available,
        "local_embeddings": check_local_embeddings_available,
        "local_whisper": check_local_whisper_available,
        "media": check_media_available,
    }

    check_func = check_funcs.get(provider)
    if not check_func:
        raise ValueError(f"Unknown provider: {provider}")

    is_available, error = check_func()
    if not is_available:
        feature_msg = f" for {feature}" if feature else ""
        raise ImportError(
            f"{provider.title()} dependencies not installed{feature_msg}.\n\n"
            f"Install with:\n  {get_install_hint(provider)}\n\n"
            f"Original error: {error}"
        )
