"""Утилиты для определения оптимального устройства для Whisper.

Функции:
    is_apple_silicon() -> bool
        Проверяет, работает ли код на Apple Silicon (M1/M2/M3/M4).

    get_device_info() -> tuple[str, str]
        Определяет лучшее доступное устройство с приоритетами:
        1. MLX (Apple Silicon) - самый быстрый для M-серии
        2. CUDA (NVIDIA GPU)
        3. MPS (Apple Silicon fallback)
        4. CPU

Переменные окружения:
    WHISPER_BACKEND: str
        Принудительный выбор backend ("mlx" или "pytorch").

Примеры:
    >>> device_type, device_name = get_device_info()
    >>> print(f"Using: {device_name}")  # "MLX (Apple Neural Engine)"

    >>> import os
    >>> os.environ["WHISPER_BACKEND"] = "pytorch"
    >>> device_type, _ = get_device_info()
    >>> print(device_type)  # "cuda" или "mps" или "cpu"
"""

import os
import platform


def is_apple_silicon() -> bool:
    """Проверяет, работает ли код на Apple Silicon (M1/M2/M3/M4).

    Returns:
        True если macOS ARM64, False в противном случае.

    Examples:
        >>> is_apple_silicon()  # На MacBook M1
        True
        >>> is_apple_silicon()  # На Windows/Linux
        False
    """
    return platform.system() == "Darwin" and platform.machine().lower() in [
        "arm64",
        "aarch64",
    ]


def get_device_info() -> tuple[str, str]:
    """Определяет лучшее доступное устройство для Whisper.

    Приоритеты:
        1. MLX (Apple Silicon) - 4-15x быстрее PyTorch MPS
        2. CUDA (NVIDIA GPU)
        3. MPS (Apple Silicon fallback)
        4. CPU

    Returns:
        Кортеж (device_type, device_name):
        - device_type: "mlx" | "cuda" | "mps" | "cpu"
        - device_name: Читаемое название устройства

    Environment Variables:
        WHISPER_BACKEND="mlx": Принудительно использовать MLX (только на Apple Silicon).
        WHISPER_BACKEND="pytorch": Принудительно использовать PyTorch (CUDA/MPS/CPU).

    Examples:
        >>> device_type, device_name = get_device_info()
        >>> print(f"{device_type}: {device_name}")
        mlx: MLX (Apple Neural Engine)

        >>> os.environ["WHISPER_BACKEND"] = "pytorch"
        >>> device_type, device_name = get_device_info()
        >>> print(device_type)  # На NVIDIA GPU
        cuda
    """
    # Проверка принудительного выбора backend через env
    force_backend = os.getenv("WHISPER_BACKEND", "").lower()

    if force_backend == "mlx" and is_apple_silicon():
        return "mlx", "MLX (Apple Neural Engine) [FORCED]"
    elif force_backend == "pytorch":
        # Принудительный PyTorch даже на Apple Silicon
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            return "cuda", f"CUDA ({gpu_name}) [FORCED]"
        elif torch.backends.mps.is_available():
            return "mps", "MPS (Apple Silicon) [FORCED]"
        else:
            return "cpu", "CPU [FORCED]"

    # Auto-detection (по умолчанию)
    if is_apple_silicon():
        # Предпочитаем MLX на Apple Silicon (4-15x быстрее MPS)
        try:
            import lightning_whisper_mlx  # noqa: F401

            return "mlx", "MLX (Apple Neural Engine)"
        except ImportError:
            # Fallback на PyTorch MPS если MLX не установлен
            try:
                import torch

                if torch.backends.mps.is_available():
                    return (
                        "mps",
                        "MPS (Apple Silicon) - Install MLX for 4-15x speedup!",
                    )
                else:
                    return "cpu", "CPU"
            except ImportError:
                return "cpu", "CPU"

    # Не-Apple платформы
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            return "cuda", f"CUDA ({gpu_name})"
        elif torch.backends.mps.is_available():
            return "mps", "MPS (Apple Silicon)"
        else:
            return "cpu", "CPU"
    except ImportError:
        return "cpu", "CPU"
