"""GLM (Zhipu AI) LLM implementation.

This module provides the GLM LLM implementation using Zhipu AI's OpenAI-compatible
API endpoint. GLM is a series of large language models from Zhipu AI (智谱 AI).

API Documentation: https://open.bigmodel.cn/dev/api

Supported models:
- glm-4: Flagship model with strong reasoning capabilities
- glm-4-flash: Fast and cost-effective model
- glm-4-plus: Enhanced version of glm-4
- glm-4-air: Lightweight model for simple tasks
- glm-4-airx: Enhanced lightweight model
"""

from __future__ import annotations

import os
from typing import Any, Optional

from src.libs.llm.openai_llm import OpenAILLM, OpenAILLMError


class GLMLLMError(OpenAILLMError):
    """Raised when GLM API call fails."""
    pass


class GLMLLM(OpenAILLM):
    """GLM (Zhipu AI) LLM provider implementation.

    This class extends OpenAILLM to work with Zhipu AI's GLM models.
    GLM uses an OpenAI-compatible API with a different base URL.

    Attributes:
        api_key: The API key for Zhipu AI (from bigmodel.cn).
        base_url: The base URL for GLM API (https://open.bigmodel.cn/api/paas/v4).
        model: The GLM model identifier (e.g., 'glm-4', 'glm-4-flash').

    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> llm = GLMLLM(settings)
        >>> response = llm.chat([Message(role='user', content='Hello')])
    """

    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the GLM LLM provider.

        Args:
            settings: Application settings containing LLM configuration.
            api_key: Optional API key override (falls back to settings.llm.api_key or env var).
            base_url: Optional base URL override.
            **kwargs: Additional configuration overrides.

        Raises:
            ValueError: If API key is not provided and not found in environment.
        """
        # Get API key from settings or environment
        glm_api_key = (
            api_key
            or getattr(settings.llm, 'api_key', None)
            or os.environ.get("GLM_API_KEY")
            or os.environ.get("ZHIPU_API_KEY")
        )

        if not glm_api_key:
            raise ValueError(
                "GLM API key not provided. Set in settings.yaml (llm.api_key), "
                "GLM_API_KEY or ZHIPU_API_KEY environment variable, or pass api_key parameter."
            )

        # Get base URL from settings or use default
        glm_base_url = (
            base_url
            or getattr(settings.llm, 'base_url', None)
            or self.DEFAULT_BASE_URL
        )

        # Initialize parent OpenAILLM with GLM-specific configuration
        super().__init__(
            settings=settings,
            api_key=glm_api_key,
            base_url=glm_base_url,
            **kwargs
        )

        # Override error class for GLM-specific error messages
        self._error_class = GLMLLMError
