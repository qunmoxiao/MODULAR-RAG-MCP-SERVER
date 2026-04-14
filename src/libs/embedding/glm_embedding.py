"""GLM (Zhipu AI) Embedding implementation.

This module provides the GLM Embedding implementation using Zhipu AI's
OpenAI-compatible API endpoint.

API Documentation: https://open.bigmodel.cn/dev/api

Supported embedding models:
- embedding-3: General-purpose embedding model (1024 dimensions)
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

from src.libs.embedding.openai_embedding import OpenAIEmbedding, OpenAIEmbeddingError


class GLMEmbeddingError(OpenAIEmbeddingError):
    """Raised when GLM Embedding API call fails."""
    pass


class GLMEmbedding(OpenAIEmbedding):
    """GLM (Zhipu AI) Embedding provider implementation.

    This class extends OpenAIEmbedding to work with Zhipu AI's embedding models.
    GLM uses an OpenAI-compatible API with a different base URL.

    Attributes:
        api_key: The API key for Zhipu AI (from bigmodel.cn).
        base_url: The base URL for GLM API (https://open.bigmodel.cn/api/paas/v4).
        model: The embedding model identifier (e.g., 'embedding-3').
        dimensions: The embedding dimension (1024 for embedding-3).

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> embedding = GLMEmbedding(settings)
        >>> vectors = embedding.embed(["hello world", "test"])
    """

    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    # GLM embedding model dimensions
    MODEL_DIMENSIONS = {
        "embedding-3": 1024,
        "embedding-2": 1024,
    }

    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the GLM Embedding provider.

        Args:
            settings: Application settings containing Embedding configuration.
            api_key: Optional API key override.
            base_url: Optional base URL override.
            **kwargs: Additional configuration overrides.

        Raises:
            ValueError: If API key is not provided and not found in environment.
        """
        # Get API key from settings or environment
        glm_api_key = (
            api_key
            or getattr(settings.embedding, 'api_key', None)
            or os.environ.get("GLM_API_KEY")
            or os.environ.get("ZHIPU_API_KEY")
        )

        if not glm_api_key:
            raise ValueError(
                "GLM API key not provided. Set in settings.yaml (embedding.api_key), "
                "GLM_API_KEY or ZHIPU_API_KEY environment variable, or pass api_key parameter."
            )

        # Get base URL from settings or use default
        glm_base_url = (
            base_url
            or getattr(settings.embedding, 'base_url', None)
            or self.DEFAULT_BASE_URL
        )

        # Initialize parent OpenAIEmbedding with GLM-specific configuration
        super().__init__(
            settings=settings,
            api_key=glm_api_key,
            base_url=glm_base_url,
            **kwargs
        )

    def get_dimension(self) -> Optional[int]:
        """Get the embedding dimension for the configured model.

        Returns:
            The embedding dimension for GLM models.
        """
        # If dimensions explicitly configured, return it
        if self.dimensions is not None:
            return self.dimensions

        # GLM model-specific defaults
        return self.MODEL_DIMENSIONS.get(self.model)
