"""Enrichers для обогащения чанков дополнительным контекстом.

Модули:
    markdown_assets: Обогащение IMAGE_REF чанков через Vision API.
"""

from semantic_core.processing.enrichers.markdown_assets import (
    MediaContext,
    MarkdownAssetEnricher,
)

__all__ = [
    "MediaContext",
    "MarkdownAssetEnricher",
]
