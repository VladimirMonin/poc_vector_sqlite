"""Image generation tool for the Gemini Media MCP server."""

import os
from datetime import datetime
from typing import List, Optional, Literal
from PIL import Image
from google import genai
from google.genai import types

from config import (
    GEMINI_API_KEY,
    IMAGE_GEN_MODELS,
    DEFAULT_IMAGE_GEN_MODEL,
    VALID_ASPECT_RATIOS,
    VALID_RESOLUTIONS,
    OUTPUT_IMAGES_DIR,
    validate_model_for_tier,
)
from utils.logger import get_logger
from utils.backup_manager import backup_generation

logger = get_logger(__name__)


def _resolve_path(path: str) -> str:
    """Converts relative paths/user inputs to absolute system paths."""
    if not path:
        return ""
    return os.path.abspath(os.path.expanduser(path))


def generate_image(
    prompt: str,
    output_path: str,
    image_paths: Optional[List[str]] = None,
    aspect_ratio: str = "16:9",
    resolution: str = "1K",
    model_type: Literal["fast", "pro"] = "fast",
) -> str:
    """
    Generate a new image from text OR edit an existing image using Google Gemini models.

    ⚠️ CRITICAL: This docstring is the PRIMARY source of truth for parameters.
    If JSON Schema shows different parameter names, ALWAYS use what's documented here.

    ⚠️ TIER REQUIREMENTS:
    - **Free Tier**: Image generation is NOT AVAILABLE. You must upgrade to Tier 1.
    - **Tier 1**: Full access to all image generation models (both 'fast' and 'pro').

    To configure your tier, set GEMINI_TIER=tier1 in your .env file.
    See https://ai.google.dev/pricing for tier details and upgrade instructions.

    Use this tool when the user wants to:
    1. Create an image from scratch (Text-to-Image).
    2. Edit an existing image (Image-to-Image / Inpainting).
    3. Transform the style of an image.

    IMPORTANT GUIDELINES FOR THE AGENT:
    1. **Prompt Translation**: You MUST translate the user's request into a detailed, descriptive ENGLISH prompt before calling this tool. Gemini image models REQUIRE English prompts for best results. Non-English prompts will produce poor quality or fail.
    2. **Output Path**: You MUST provide a valid, absolute file path for `output_path`. Ask the user for a location if unclear, or determine a sensible path based on the user's environment (e.g., Desktop or project folder).
    3. **Editing**: If the user wants to edit an image, you MUST provide the absolute path to that image in `image_paths` and describe the desired result in the `prompt` (e.g., "A photo of a cat wearing a wizard hat").
    4. **Model Selection**:
       - Use `model_type='fast'` (Gemini 2.5 Flash) for quick drafts, iterations, or when speed is priority. Note: It ONLY supports '1K' resolution.
       - Use `model_type='pro'` (Gemini 3 Pro) for high-quality art, precise text rendering within images, complex instruction following, or when '2K' resolution is requested.

    Args:
        prompt (str): A highly detailed description of the desired image in ENGLISH.
        output_path (str): REQUIRED. The absolute path where the generated image file will be saved (e.g., "C:/Users/User/Desktop/result.png").
        image_paths (Optional[List[str]]): List of absolute file paths to reference images (for editing, style transfer, or composition). Max 5 images.
        aspect_ratio (str): The aspect ratio of the output image.
                            Allowed values: '1:1', '16:9', '9:16', '4:3', '3:4', '2:3', '3:2', '4:5', '5:4', '21:9'.
                            Default is '16:9'.
        resolution (str): The output resolution. Allowed values: '1K', '2K'.
                          Note: '2K' is ONLY supported when `model_type` is 'pro'. If 'fast' is selected, this will be forced to '1K'.
        model_type (Literal['fast', 'pro']): Selects the underlying model. 'fast' is faster/cheaper, 'pro' is higher quality. Default is 'fast'.

    Returns:
        str: The absolute path to the saved image file on success.
    """
    # --- 0. Pre-validation logging ---
    logger.info(
        f"🎨 Image Gen Request: model={model_type}, res={resolution}, ar={aspect_ratio}"
    )
    logger.info(f"💾 Target Output: {output_path}")

    # --- 0.5. Tier Validation (CRITICAL for Free tier users) ---
    # Проверяем доступность генерации изображений на текущем tier
    is_available, error_message = validate_model_for_tier("", "image_generation")
    if not is_available:
        logger.error(f"❌ {error_message}")
        raise ValueError(error_message)

    # --- 1. Validate Output Path (Critical) ---
    if not output_path:
        raise ValueError(
            "output_path is missing. The agent must specify an absolute path to save the file."
        )

    final_path = _resolve_path(output_path)

    # Check if path is a directory (it must be a file)
    if os.path.isdir(final_path):
        raise ValueError(
            f"output_path '{final_path}' is a directory. Please specify a full file path including the filename (e.g., .../image.png)."
        )

    # Ensure valid extension
    if not final_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        final_path += ".png"
        logger.info(f"🔄 Appended extension: {final_path}")

    # --- 2. Validate Parameters ---
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        logger.warning(
            f"⚠️ Invalid aspect_ratio '{aspect_ratio}'. Resetting to default '16:9'."
        )
        aspect_ratio = "16:9"

    if resolution not in VALID_RESOLUTIONS:
        logger.warning(f"⚠️ Invalid resolution '{resolution}'. Resetting to '1K'.")
        resolution = "1K"

    # API Limit Check: Flash model only supports 1K
    if model_type == "fast" and resolution != "1K":
        logger.warning(
            f"⚠️ Model 'fast' (Flash) does not support {resolution}. Downgrading to 1K."
        )
        resolution = "1K"

    # Resolve model name from config
    selected_model = IMAGE_GEN_MODELS.get(
        model_type, IMAGE_GEN_MODELS.get(DEFAULT_IMAGE_GEN_MODEL)
    )
    if not selected_model:
        selected_model = "gemini-2.5-flash-image"  # Hard fallback

    # --- 3. Prepare Content (Prompt + Images) ---
    contents = [prompt]

    if image_paths:
        valid_images_count = 0
        for raw_path in image_paths:
            path = _resolve_path(raw_path)
            if os.path.exists(path):
                try:
                    # Gemini SDK handles PIL images natively in contents list
                    img = Image.open(path)
                    contents.append(img)
                    valid_images_count += 1
                    logger.debug(f"📎 Loaded reference image: {path}")
                except Exception as e:
                    logger.error(f"❌ Failed to load reference image {path}: {e}")
            else:
                logger.error(f"❌ Reference image not found at path: {path}")

        # If inputs were provided but none were valid, fail fast
        if valid_images_count == 0 and image_paths:
            raise FileNotFoundError(
                f"Could not load any of the provided reference images: {image_paths}"
            )

    # --- 4. Configure and Call API ---
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        # Construct ImageConfig
        # Only pass image_size if strictly necessary to avoid Pydantic validation errors in SDK
        img_config_params = {"aspect_ratio": aspect_ratio}

        if model_type == "pro" and resolution != "1K":
            img_config_params["image_size"] = resolution

        gen_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],  # We only want the image blob
            image_config=types.ImageConfig(**img_config_params),
        )

        logger.info(f"🚀 Sending request to Gemini ({selected_model})...")
        logger.info(f"📝 Prompt (start): {prompt[:100]}...")

        response = client.models.generate_content(
            model=selected_model, contents=contents, config=gen_config
        )

        # --- 5. Handle Response ---
        if not response.candidates:
            # Usually happens if safety filters block the request
            raise ValueError(
                "API returned no candidates. The prompt might have triggered safety filters."
            )

        generated_image_part = None
        # Iterate through parts to find the inline_data (image blob)
        if response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    generated_image_part = part
                    break

        if not generated_image_part:
            # Extract text error if present
            text_error = "Unknown error"
            if response.candidates[0].content and response.candidates[0].content.parts:
                text_part = response.candidates[0].content.parts[0]
                if text_part.text:
                    text_error = text_part.text

            raise ValueError(
                f"Model returned text instead of an image. This often means the model refused the request. Response: {text_error}"
            )

        # --- 6. Save to Disk ---
        image_bytes = generated_image_part.inline_data.data

        # Ensure directory exists
        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        with open(final_path, "wb") as f:
            f.write(image_bytes)

        logger.info(f"✅ Image successfully saved to: {final_path}")

        # --- Backup to output/images/ with metadata ---
        try:
            backup_metadata = {
                "timestamp": datetime.now().isoformat(),
                "file_path": final_path,
                "parameters": {
                    "prompt": prompt,
                    "model_type": model_type,
                    "model": selected_model,
                    "aspect_ratio": aspect_ratio,
                    "resolution": resolution,
                    "reference_images": image_paths if image_paths else None,
                },
            }
            backup_path, metadata_path = backup_generation(
                original_path=final_path,
                file_type="image",
                metadata=backup_metadata,
            )
            logger.info(f"📦 Backup created: {backup_path}")
        except Exception as backup_error:
            logger.warning(f"⚠️ Backup failed (non-critical): {backup_error}")

        return final_path

    except Exception as e:
        logger.exception(f"❌ Image generation process failed: {e}")
        # Return a clean error message to the agent
        return f"Error generating image: {str(e)}"
