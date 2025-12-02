"""Audio analysis tool for the Gemini Media MCP server."""

import json
import os

from config import (
    AVAILABLE_AUDIO_ANALYSIS_PROMPTS,
    DEFAULT_GEMINI_MODEL,
    GEMINI_MODELS,
    MAX_FILE_SIZE_MB,
    SUPPORTED_AUDIO_FORMATS,
)
from models.analysis import AudioAnalysisResponse, ErrorResponse
from utils.gemini_client import GeminiClient
from utils.logger import get_logger

logger = get_logger(__name__)


def get_system_instruction(
    name: str = "default",
    override: str | None = None,
    file_path: str | None = None,
    prompts_dict: dict = AVAILABLE_AUDIO_ANALYSIS_PROMPTS,
) -> str | None:
    """Get system instruction with priority handling.

    Priority order:
    1. File path (highest priority)
    2. Custom override
    3. Predefined instruction by name

    Args:
        name: Name of predefined system instruction.
        override: Custom system instruction string.
        file_path: Path to file with system instruction.
        prompts_dict: Dictionary containing predefined prompts.

    Returns:
        System instruction string or None if not found.

    Raises:
        FileNotFoundError: If system instruction file not found.
        IOError: If error reading system instruction file.
    """
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    if override:
        return override
    return prompts_dict.get(name)


def analyze_audio(
    audio_path: str,
    user_prompt: str = "",
    model_name: str | None = None,
    system_instruction_name: str = "default",
    system_instruction_override: str | None = None,
    system_instruction_file_path: str | None = None,
) -> AudioAnalysisResponse | ErrorResponse:
    """Analyzes an audio file using the Gemini API.

    ⚠️ CRITICAL: This docstring is the PRIMARY source of truth for parameters.
    If JSON Schema shows different parameter names, ALWAYS use what's documented here.

    Returns structured analysis response with title, summary, transcription,
    participants, hashtags, and action items.

    Args:
        audio_path: Absolute path to the audio file on local machine.
        user_prompt: Custom analysis request (optional).
        model_name: The Gemini model to use (e.g., "gemini-2.5-flash").
                    Defaults to the one specified in config.py.
        system_instruction_name: Name of predefined system instruction.
        system_instruction_override: Custom system instruction (overrides system_instruction_name).
        system_instruction_file_path: Path to file with system instruction (highest priority).

    Returns:
        Structured analysis response or error response.

    Raises:
        ValueError: If audio file is invalid or system instruction not found.
        FileNotFoundError: If audio file or system instruction file not found.
        IOError: If error reading files.
    """
    logger.info("=" * 80)
    logger.info(f"🎵 AUDIO ANALYSIS STARTED: {audio_path}")

    # Validate audio file exists
    if not os.path.exists(audio_path):
        logger.error(f"❌ Audio file not found: {audio_path}")
        raise FileNotFoundError(f"Audio file not found at {audio_path}")

    # Validate file size
    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    logger.info(f"📁 File size: {file_size_mb:.2f} MB")
    if file_size_mb > MAX_FILE_SIZE_MB:
        logger.error(
            f"❌ File size exceeds limit: {file_size_mb:.2f} MB > {MAX_FILE_SIZE_MB} MB"
        )
        raise ValueError(
            f"File size ({file_size_mb:.2f} MB) exceeds the limit of {MAX_FILE_SIZE_MB} MB."
        )

    # Validate audio format
    import mimetypes

    mime_type, _ = mimetypes.guess_type(audio_path)
    logger.info(f"🎧 Format: {mime_type}")
    if mime_type not in SUPPORTED_AUDIO_FORMATS:
        logger.error(f"❌ Unsupported format: {mime_type}")
        raise ValueError(
            f"Unsupported audio format: {mime_type}. "
            f"Supported formats: {list(SUPPORTED_AUDIO_FORMATS.keys())}"
        )

    # Get system instruction
    try:
        system_instruction = get_system_instruction(
            name=system_instruction_name,
            override=system_instruction_override,
            file_path=system_instruction_file_path,
            prompts_dict=AVAILABLE_AUDIO_ANALYSIS_PROMPTS,
        )
    except FileNotFoundError as e:
        logger.error(f"System instruction file not found: {e}")
        raise
    except IOError as e:
        logger.error(f"Error reading system instruction file: {e}")
        raise

    # Check if system instruction exists
    if system_instruction is None and system_instruction_name:
        available = list(AVAILABLE_AUDIO_ANALYSIS_PROMPTS.keys())
        raise ValueError(
            f"Prompt '{system_instruction_name}' not found. Available: {available}"
        )

    # Select and validate model
    final_model_name = model_name or DEFAULT_GEMINI_MODEL
    if final_model_name not in GEMINI_MODELS:
        raise ValueError(
            f"Model '{final_model_name}' is not supported. "
            f"Available models: {GEMINI_MODELS}"
        )

    logger.info(
        f"📊 Parameters: model={final_model_name}, system_instruction={system_instruction_name}"
    )

    # Initialize client and perform analysis
    try:
        logger.info(
            f"🚀 Sending {file_size_mb:.2f} MB audio to Gemini ({final_model_name})..."
        )
        gemini_client = GeminiClient(model_name=final_model_name)

        # Read audio file as bytes
        with open(audio_path, "rb") as audio_file:
            audio_bytes = audio_file.read()

        response_text = gemini_client.generate_content(
            prompt=user_prompt,
            media_bytes=audio_bytes,
            mime_type=mime_type,
            system_instruction=system_instruction,
            response_schema=AudioAnalysisResponse,
        )

        # Parse and validate response using Pydantic
        try:
            result_dict = json.loads(response_text)
            result = AudioAnalysisResponse(**result_dict)
            logger.info(f"✅ Audio analysis completed successfully for {audio_path}")
            logger.info(
                f"📈 Summary: {file_size_mb:.2f} MB audio processed with {final_model_name}"
            )
            logger.info("=" * 80)
            return result
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"❌ Failed to parse JSON response: {e}")
            logger.error("=" * 80)
            return ErrorResponse(
                error="JSON parsing error",
                details=str(e),
                raw_response=response_text,
            )

    except Exception as e:
        logger.exception(
            f"❌ Failed to analyze audio with model {final_model_name}: {e}"
        )
        logger.error("=" * 80)
        return ErrorResponse(
            error="Audio analysis failed",
            details=str(e),
        )
