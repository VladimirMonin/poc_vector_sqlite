"""Video analysis tool for the Gemini Media MCP server.

This tool analyzes videos by extracting frames and audio, then sending
them together to Gemini API in a single multimodal request for comprehensive
analysis combining visual and audio information.
"""

import json
import os
from typing import Optional, Literal

from google import genai
from google.genai import types

from config import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_API_KEY,
)
from models.analysis import VideoAnalysisResponse, ErrorResponse
from utils.media_frame_extractor import extract_frames
from utils.audio_extractor import extract_audio_from_video, estimate_audio_size
from utils.logger import get_logger

logger = get_logger(__name__)

# Gemini API inline limit (20MB for all content)
GEMINI_INLINE_LIMIT_MB = 20.0

# Default system prompt for video analysis
DEFAULT_VIDEO_SYSTEM_PROMPT = """You are analyzing a video by examining extracted frames and audio track.

**Your Task:**
1. **Visual Analysis**: Examine the sequence of frames to understand what's happening visually
2. **Audio Analysis**: Transcribe speech and describe non-speech sounds (music, effects, ambient)
3. **Combined Narrative**: Create a coherent story that integrates both visual and audio information

**Important Guidelines:**
- Frames are extracted at intervals, so consider the flow and progression between them
- Look for cause-and-effect relationships between visual and audio elements
- Identify key moments where visual and audio reinforce each other
- Note any discrepancies or interesting contrasts between what's seen and heard

Provide your analysis in a structured format that separates visual, audio, and combined insights."""


def analyze_video(
    video_path: str,
    prompt: str = "Analyze this video content, describing what you see and hear.",
    # Frame extraction modes
    frame_mode: Literal["fps", "total", "interval"] = "total",
    frame_count: Optional[int] = 10,
    fps: Optional[float] = None,
    interval_sec: Optional[float] = None,
    # Frame quality
    max_dimension: int = 1920,
    image_format: Literal["webp", "jpeg"] = "webp",
    image_quality: int = 80,
    # Audio options
    include_audio: bool = True,
    audio_bitrate: Literal[64, 32, 24] = 64,
    # Utility
    dry_run: bool = False,
    # Model selection
    model_name: str = DEFAULT_GEMINI_MODEL,
) -> str:
    """Analyze video as frames + audio in one multimodal request.

    ⚠️ CRITICAL: This docstring is the PRIMARY source of truth for parameters.
    If JSON Schema shows different parameter names, ALWAYS use what's documented here.
    For best results, provide prompts in ENGLISH.

    Extracts video frames and audio track, optimizes them, and sends to Gemini API
    for comprehensive analysis. Supports dry-run mode to estimate request size
    before processing.

    Args:
        video_path: Absolute path to video file
        prompt: Analysis request prompt (default: general analysis)
        frame_mode: Frame extraction mode ('total', 'fps', 'interval')
        frame_count: Number of frames for 'total' mode (default: 10)
        fps: Frames per second for 'fps' mode (e.g., 0.5 = 1 frame every 2 sec)
        interval_sec: Interval in seconds for 'interval' mode
        max_dimension: Max dimension for frame resize (default: 1920 for 1080p)
        image_format: Frame format ('webp' or 'jpeg', default: 'webp')
        image_quality: Compression quality 1-100 (default: 80)
        include_audio: Whether to extract and analyze audio (default: True)
        audio_bitrate: Audio bitrate in kbps (64/32/24, default: 64)
        dry_run: If True, only estimate size without processing (default: False)
        model_name: Gemini model to use (default from config)

    Returns:
        JSON string with VideoAnalysisResponse or dry-run estimation

    Raises:
        FileNotFoundError: If video file not found
        ValueError: If parameters invalid or request too large
        RuntimeError: If analysis fails

    Examples:
        # Basic analysis with 30 frames
        result = analyze_video("lecture.mp4", frame_count=30)

        # Extract at 0.5 FPS (1 frame every 2 seconds)
        result = analyze_video("video.mp4", frame_mode="fps", fps=0.5)

        # Extract frame every 10 seconds, low audio bitrate
        result = analyze_video(
            "long_video.mp4",
            frame_mode="interval",
            interval_sec=10,
            audio_bitrate=32
        )

        # Dry run to check size before processing
        estimate = analyze_video("large.mp4", dry_run=True)
        # Returns: {"estimated_size_mb": 18.5, "fits_in_limit": true, ...}
    """
    logger.info("=" * 80)
    logger.info(f"🎬 VIDEO ANALYSIS STARTED: {video_path}")
    logger.info(f"Mode: {frame_mode}, Audio: {include_audio}, Dry run: {dry_run}")

    # Validate video file
    if not os.path.exists(video_path):
        logger.error(f"❌ Video file not found: {video_path}")
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # DRY RUN MODE: Quick estimation
    if dry_run:
        logger.info("🔍 DRY RUN: Estimating request size...")
        return _estimate_request_size(
            video_path=video_path,
            frame_mode=frame_mode,
            frame_count=frame_count,
            fps=fps,
            interval_sec=interval_sec,
            max_dimension=max_dimension,
            image_format=image_format,
            image_quality=image_quality,
            include_audio=include_audio,
            audio_bitrate=audio_bitrate,
        )

    # NORMAL MODE: Extract and analyze
    try:
        # Step 1: Extract frames
        logger.info(f"📸 Extracting frames (mode={frame_mode})...")
        frames_b64, frames_meta = extract_frames(
            source=video_path,
            mode=frame_mode,
            frame_count=frame_count,
            fps=fps,
            interval_sec=interval_sec,
            max_dimension=max_dimension,
            output_format=image_format,
            quality=image_quality,
        )

        total_size_mb = frames_meta["total_size_mb"]
        logger.info(
            f"✅ Frames: {frames_meta['frame_count']} @ {frames_meta['resolution']}, "
            f"size: {total_size_mb:.2f} MB"
        )

        # Step 2: Extract audio (if requested)
        audio_data = None
        if include_audio:
            logger.info(f"🎵 Extracting audio (bitrate={audio_bitrate} kbps)...")
            audio_data = extract_audio_from_video(
                video_path=video_path, bitrate=audio_bitrate, dry_run=False
            )
            audio_size_mb = audio_data["size_mb"]
            total_size_mb += audio_size_mb
            logger.info(
                f"✅ Audio: {audio_data['duration_sec']}s, size: {audio_size_mb:.2f} MB"
            )
        else:
            logger.info("⏭️  Skipping audio extraction (include_audio=False)")

        # Step 3: Check total size
        logger.info(f"📊 Total request size: {total_size_mb:.2f} MB")
        if total_size_mb > GEMINI_INLINE_LIMIT_MB:
            logger.error(
                f"❌ Request too large: {total_size_mb:.2f} MB > {GEMINI_INLINE_LIMIT_MB} MB"
            )
            raise ValueError(
                f"Request size ({total_size_mb:.2f} MB) exceeds Gemini inline limit "
                f"({GEMINI_INLINE_LIMIT_MB} MB). Try reducing frame_count, using lower "
                f"audio_bitrate, or smaller max_dimension."
            )

        usage_percent = (total_size_mb / GEMINI_INLINE_LIMIT_MB) * 100
        logger.info(f"✅ Size check passed ({usage_percent:.1f}% of limit)")

        # Step 4: Build multimodal request
        logger.info("🔨 Building multimodal request...")
        contents = _build_multimodal_contents(
            prompt=prompt,
            frames_b64=frames_b64,
            image_format=image_format,
            audio_data=audio_data,
        )

        # Step 5: Send to Gemini API
        logger.info(f"🚀 Sending to Gemini API (model={model_name})...")
        client = genai.Client(api_key=GEMINI_API_KEY)

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=DEFAULT_VIDEO_SYSTEM_PROMPT,
                temperature=0.4,
                response_mime_type="application/json",
                response_schema=VideoAnalysisResponse,
            ),
        )

        # Step 6: Parse response
        raw_text = response.text
        logger.info(f"📥 Received response ({len(raw_text)} chars)")

        try:
            parsed = json.loads(raw_text)
            # Add raw_text to response
            parsed["raw_text"] = raw_text

            # Validate with Pydantic
            validated_response = VideoAnalysisResponse(**parsed)
            result_json = validated_response.model_dump_json(indent=2)

            logger.info("✅ VIDEO ANALYSIS COMPLETE")
            logger.info("=" * 80)

            return result_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            error_response = ErrorResponse(
                error="Invalid JSON response from Gemini API",
                details=str(e),
                raw_response=raw_text,
            )
            return error_response.model_dump_json(indent=2)

        except Exception as e:
            logger.error(f"Failed to validate response: {e}")
            error_response = ErrorResponse(
                error="Response validation failed",
                details=str(e),
                raw_response=raw_text,
            )
            return error_response.model_dump_json(indent=2)

    except (FileNotFoundError, ValueError):
        raise
    except Exception as e:
        logger.exception(f"Video analysis failed: {e}")
        raise RuntimeError(f"Video analysis failed: {e}")


def _estimate_request_size(
    video_path: str,
    frame_mode: str,
    frame_count: Optional[int],
    fps: Optional[float],
    interval_sec: Optional[float],
    max_dimension: int,
    image_format: str,
    image_quality: int,
    include_audio: bool,
    audio_bitrate: int,
) -> str:
    """Estimate request size without processing (dry-run mode).

    Returns JSON with size estimation and recommendations.
    """
    # Get audio metadata for duration
    from utils.audio_extractor import get_audio_metadata

    try:
        audio_meta = get_audio_metadata(video_path)
        duration_sec = audio_meta["duration_sec"]
    except Exception as e:
        logger.warning(f"Could not get audio metadata: {e}")
        duration_sec = 0.0

    # Estimate frames size (rough calculation)
    # Average frame size depends on format and quality
    if image_format == "webp":
        if max_dimension >= 1920:  # 1080p
            avg_frame_kb = 100 if image_quality >= 80 else 70
        elif max_dimension >= 1280:  # 720p
            avg_frame_kb = 50 if image_quality >= 80 else 35
        else:  # 480p and below
            avg_frame_kb = 25 if image_quality >= 80 else 18
    else:  # JPEG
        if max_dimension >= 1920:
            avg_frame_kb = 130 if image_quality >= 80 else 90
        elif max_dimension >= 1280:
            avg_frame_kb = 65 if image_quality >= 80 else 45
        else:
            avg_frame_kb = 35 if image_quality >= 80 else 25

    # Calculate frame count based on mode
    if frame_mode == "total":
        est_frame_count = frame_count or 10
    elif frame_mode == "fps":
        est_frame_count = int(duration_sec * (fps or 1.0))
    elif frame_mode == "interval":
        est_frame_count = int(duration_sec / (interval_sec or 10.0))
    else:
        est_frame_count = 10

    frames_size_mb = (est_frame_count * avg_frame_kb) / 1024

    # Estimate audio size
    audio_size_mb = 0.0
    if include_audio and duration_sec > 0:
        audio_size_mb = estimate_audio_size(duration_sec, audio_bitrate)

    # Total size
    total_size_mb = frames_size_mb + audio_size_mb
    fits_in_limit = total_size_mb < GEMINI_INLINE_LIMIT_MB
    usage_percent = (total_size_mb / GEMINI_INLINE_LIMIT_MB) * 100

    # Build recommendation
    if fits_in_limit:
        if usage_percent < 50:
            recommendation = f"Safe to send ({usage_percent:.0f}% of {GEMINI_INLINE_LIMIT_MB} MB limit)"
        elif usage_percent < 75:
            recommendation = f"Good fit ({usage_percent:.0f}% of limit)"
        else:
            recommendation = (
                f"Close to limit ({usage_percent:.0f}%), consider optimizing"
            )
    else:
        exceed_mb = total_size_mb - GEMINI_INLINE_LIMIT_MB
        recommendation = f"❌ Exceeds limit by {exceed_mb:.1f} MB! Reduce frame_count or audio_bitrate"

    result = {
        "estimated_size_mb": round(total_size_mb, 2),
        "fits_in_limit": fits_in_limit,
        "usage_percent": round(usage_percent, 1),
        "frames": {
            "count": est_frame_count,
            "mode": frame_mode,
            "resolution": f"~{max_dimension}p",
            "format": image_format,
            "size_mb": round(frames_size_mb, 2),
        },
        "audio": {
            "duration_sec": round(duration_sec, 1),
            "bitrate_kbps": audio_bitrate if include_audio else 0,
            "size_mb": round(audio_size_mb, 2),
        }
        if include_audio
        else None,
        "recommendation": recommendation,
    }

    logger.info(f"📊 Dry-run estimation: {total_size_mb:.2f} MB ({recommendation})")

    return json.dumps(result, indent=2)


def _build_multimodal_contents(
    prompt: str,
    frames_b64: list[str],
    image_format: str,
    audio_data: Optional[dict],
) -> list:
    """Build multimodal contents array for Gemini API.

    Args:
        prompt: User prompt
        frames_b64: List of base64-encoded frames
        image_format: 'webp' or 'jpeg'
        audio_data: Audio data dict with 'base64' and 'mime_type' (or None)

    Returns:
        List of content parts for Gemini API
    """
    contents = []

    # Add text prompt first
    contents.append(prompt)

    # Add all frames
    mime_type = f"image/{image_format}"
    for i, frame_b64 in enumerate(frames_b64, 1):
        contents.append(types.Part.from_bytes(data=frame_b64, mime_type=mime_type))

    logger.info(f"Added {len(frames_b64)} frames to request")

    # Add audio if available
    if audio_data:
        audio_b64 = audio_data["base64"]
        audio_mime = audio_data["mime_type"]
        contents.append(types.Part.from_bytes(data=audio_b64, mime_type=audio_mime))
        logger.info(f"Added audio to request ({audio_data['duration_sec']}s)")

    return contents
