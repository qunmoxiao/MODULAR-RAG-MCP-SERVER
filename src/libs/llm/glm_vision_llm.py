"""GLM (Zhipu AI) Vision LLM implementation.

This module provides the GLM Vision LLM implementation for multimodal
interactions (text + image) using Zhipu AI's GLM-4V model.

API Documentation: https://open.bigmodel.cn/dev/api

Supported vision models:
- glm-4v: Vision-capable model for image understanding
"""

from __future__ import annotations

import os
from typing import Any, Optional

from src.libs.llm.openai_vision_llm import OpenAIVisionLLM, OpenAIVisionLLMError


class GLMVisionLLMError(OpenAIVisionLLMError):
    """Raised when GLM Vision API call fails."""
    pass


class GLMVisionLLM(OpenAIVisionLLM):
    """GLM (Zhipu AI) Vision LLM provider implementation.

    This class extends OpenAIVisionLLM to work with Zhipu AI's GLM-4V model.
    GLM-4V supports multimodal input (text + image) for image captioning,
    visual question answering, and document understanding.

    Attributes:
        api_key: The API key for Zhipu AI (from bigmodel.cn).
        base_url: The base URL for GLM API (https://open.bigmodel.cn/api/paas/v4).
        model: The GLM Vision model identifier (e.g., 'glm-4v').

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> vision_llm = GLMVisionLLM(settings)
        >>> image = ImageInput(path="diagram.png")
        >>> response = vision_llm.chat_with_image("Describe this", image)
    """

    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_image_size: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the GLM Vision LLM provider.

        Args:
            settings: Application settings containing vision_llm configuration.
            api_key: Optional API key override.
            base_url: Optional base URL override.
            max_image_size: Maximum image dimension in pixels for auto-compression.
            **kwargs: Additional configuration overrides.

        Raises:
            ValueError: If required configuration is missing.
        """
        # Get vision settings section
        vision_settings = getattr(settings, "vision_llm", None)

        # Get API key from settings or environment
        glm_api_key = api_key
        if not glm_api_key and vision_settings:
            glm_api_key = getattr(vision_settings, 'api_key', None)
        if not glm_api_key:
            glm_api_key = getattr(settings.llm, 'api_key', None)
        if not glm_api_key:
            glm_api_key = os.environ.get("GLM_API_KEY")
        if not glm_api_key:
            glm_api_key = os.environ.get("ZHIPU_API_KEY")

        if not glm_api_key:
            raise ValueError(
                "GLM API key not provided. Set in settings.yaml (vision_llm.api_key), "
                "GLM_API_KEY or ZHIPU_API_KEY environment variable, or pass api_key parameter."
            )

        # Get base URL from settings or use default
        glm_base_url = base_url
        if not glm_base_url and vision_settings:
            glm_base_url = getattr(vision_settings, 'base_url', None)
        if not glm_base_url:
            glm_base_url = getattr(settings.llm, 'base_url', None)
        if not glm_base_url:
            glm_base_url = self.DEFAULT_BASE_URL

        # Initialize parent OpenAIVisionLLM with GLM-specific configuration
        super().__init__(
            settings=settings,
            api_key=glm_api_key,
            base_url=glm_base_url,
            max_image_size=max_image_size,
            **kwargs
        )

        # Override error class for GLM-specific error messages
        self._error_class = GLMVisionLLMError
