"""GIF animation analysis tool using Google Gemini API."""

from typing import Literal, Optional
from PIL import Image

from config import (
    GIF_QUALITY_PRESETS,
    DEFAULT_GIF_QUALITY,
    DEFAULT_GIF_MODEL,
    DEFAULT_GIF_ANALYSIS_SYSTEM_PROMPT,
    GIF_USER_GUIDELINES,
)
from utils.gif_processor import (
    extract_gif_frames,
    resize_image,
    create_animation_prompt,
)
from utils.image_tokens import calculate_images_tokens, estimate_cost
from utils.gemini_client import GeminiClient
from utils.logger import get_logger

logger = get_logger(__name__)


async def analyze_gif(
    image_path: str,
    prompt: str = "Analyze this animation and describe what it demonstrates",
    mode: Literal["fps", "total", "interval"] = "total",
    gif_fps: Optional[float] = None,
    frame_count: int = 5,
    interval_sec: Optional[float] = None,
    quality: Literal["uhd", "fhd", "hd", "balanced", "economy"] = DEFAULT_GIF_QUALITY,
    model: str = DEFAULT_GIF_MODEL,
) -> dict:
    """Analyze GIF animation using Gemini AI.

    ⚠️ CRITICAL: This docstring is the PRIMARY source of truth for parameters.
    If JSON Schema shows different parameter names, ALWAYS use what's documented here.
    For best results, provide prompts in ENGLISH.

    This tool extracts key frames from GIF animations and analyzes them as a cohesive sequence,
    understanding both individual frames and the overall narrative/purpose of the animation.

    Args:
        image_path: Path to GIF file (local path or URL)
        prompt: Your specific question or analysis request. The default system prompt already
                explains this is an animation, so add context like:
                - "This is a VS Code tutorial showing..."
                - "This demonstrates a chatbot conversation..."
                - "This shows terminal commands..."
        mode: Extraction strategy:
              - 'total' (RECOMMENDED): Extract fixed number of evenly distributed frames
              - 'fps': Extract frames at specified rate (frames per second)
              - 'interval': Extract frames at fixed time intervals
        gif_fps: Frames per second to extract (for 'fps' mode, e.g., 1.0 = 1 frame/sec)
        frame_count: Number of frames to extract (for 'total' mode, default: 5)
                    - 5 frames: Quick demos (10-30s)
                    - 10 frames: Detailed tutorials (30-90s)
                    - 15+ frames: Long sessions (2+ min)
        interval_sec: Time interval in seconds (for 'interval' mode, e.g., 5.0 = every 5 sec)
        quality: Image quality preset (default: 'fhd' for 1080p):
                - 'fhd' (1920px): Best for UI tutorials with text (RECOMMENDED)
                - 'hd' (1280px): Good balance for general animations
                - 'balanced' (960px): Budget-friendly for long sessions
                - 'economy' (768px): Minimal quality, lowest cost
                - 'uhd' (original): Maximum detail, highest cost
        model: Gemini model to use (default: 'gemini-2.5-flash')

    Returns:
        dict: {
            "analysis": str,           # AI analysis of the animation
            "metadata": {
                "frame_count": int,    # Number of frames analyzed
                "mode": str,           # Extraction mode used
                "quality": str,        # Quality preset used
                "estimated_tokens": int, # Approximate token usage
                "model": str,          # Model used
                "extraction_params": dict
            }
        }

    Examples:
        # Quick UI tutorial analysis (RECOMMENDED)
        result = await analyze_gif(
            "tutorial.gif",
            prompt="This is a VS Code feature demo. Describe each step.",
            frame_count=5,
            quality='fhd'
        )

        # Detailed workflow analysis
        result = await analyze_gif(
            "workflow.gif",
            prompt="Explain this design process",
            frame_count=10,
            quality='fhd'
        )

        # Budget-friendly long session
        result = await analyze_gif(
            "long_session.gif",
            prompt="Summarize this terminal session",
            frame_count=10,
            quality='balanced'
        )

        # FPS mode for time-sensitive analysis
        result = await analyze_gif(
            "animation.gif",
            mode='fps',
            gif_fps=1.0,
            quality='hd'
        )
    """
    try:
        logger.info("=" * 80)
        logger.info(f"🎬 GIF ANALYSIS STARTED: {image_path}")
        logger.info(f"📊 Parameters: mode={mode}, quality={quality}, model={model}")
        logger.info(
            f"🔧 Extraction: frame_count={frame_count}, gif_fps={gif_fps}, interval_sec={interval_sec}"
        )

        # Load GIF
        image = Image.open(image_path)

        if not getattr(image, "is_animated", False):
            logger.warning(f"❌ File is not animated: {image_path}")
            return {
                "error": "File is not an animated GIF",
                "suggestion": "Use 'analyze_image' tool for static images",
            }

        # Extract frames
        frames = extract_gif_frames(
            image,
            mode=mode,
            gif_fps=gif_fps,
            frame_count=frame_count,
            interval_sec=interval_sec,
        )

        logger.info(f"✅ Extracted {len(frames)} frames from animation")

        # Resize frames based on quality preset
        max_dimension = GIF_QUALITY_PRESETS.get(quality, 1920)
        processed_frames = [resize_image(f, max_dimension) for f in frames]

        # Calculate tokens using centralized module
        token_info = calculate_images_tokens(processed_frames)
        logger.info(f"💰 Token calculation:\n{token_info['breakdown']}")

        # Estimate cost
        cost_info = estimate_cost(token_info["total_tokens"], model)
        logger.info(
            f"💵 Estimated cost: ${cost_info['estimated_input_cost_usd']:.6f} USD "
            f"({token_info['total_tokens']:,} tokens @ {model})"
        )

        # Create extraction info for prompt
        if mode == "fps":
            fps_value = gif_fps if gif_fps else 1.0
            extraction_info = f"Extracted at {fps_value} FPS (1 frame every {1.0 / fps_value:.1f} seconds)"
        elif mode == "total":
            extraction_info = (
                f"{len(frames)} frames evenly distributed across the entire animation"
            )
        else:  # interval
            extraction_info = f"Frames extracted every {interval_sec} seconds"

        # Create enhanced prompt with system prompt
        enhanced_prompt = create_animation_prompt(
            prompt,
            len(processed_frames),
            extraction_info,
            DEFAULT_GIF_ANALYSIS_SYSTEM_PROMPT,
        )

        # Call Gemini API with multi-image method
        logger.info(f"🚀 Sending {len(processed_frames)} frames to Gemini ({model})...")
        client = GeminiClient(model_name=model)

        response_text = client.generate_content_multi_image(
            prompt=enhanced_prompt,
            images=processed_frames,  # List of PIL Images
            temperature=0.7,
        )

        logger.info(f"✅ Analysis completed successfully for {image_path}")
        logger.info(
            f"📈 Summary: {len(frames)} frames, {token_info['total_tokens']:,} tokens, "
            f"${cost_info['estimated_input_cost_usd']:.6f} USD"
        )
        logger.info("=" * 80)

        return {
            "analysis": response_text,
            "metadata": {
                "frame_count": len(frames),
                "mode": mode,
                "quality": quality,
                "tokens": token_info,
                "estimated_cost": cost_info,
                "model": model,
                "extraction_params": {
                    "gif_fps": gif_fps,
                    "frame_count": frame_count,
                    "interval_sec": interval_sec,
                },
            },
        }

    except FileNotFoundError:
        logger.error(f"❌ File not found: {image_path}")
        return {
            "error": "File not found",
            "path": image_path,
        }
    except Exception as e:
        logger.exception("GIF analysis failed")
        return {
            "error": "GIF analysis failed",
            "details": str(e),
        }


async def get_gif_guidelines() -> str:
    """Get comprehensive guidelines for GIF animation analysis.

    Returns best practices, quality recommendations, cost estimates,
    and example workflows for analyzing GIF animations.

    Returns:
        str: Formatted guidelines text
    """
    return GIF_USER_GUIDELINES
