"""
Exception types for SIE AutoPPT workflows.

This module centralizes all custom exception types to improve error handling
and allow callers to distinguish between different failure scenarios.
"""


class AiWorkflowError(RuntimeError):
    """
    Raised when AI planning workflow encounters a general error.

    This includes configuration errors, API errors, external planner errors,
    and validation errors during the AI planning process.
    """
    pass


class AiHealthcheckBlockedError(RuntimeError):
    """
    Raised when AI healthcheck cannot proceed due to configuration issues.

    This typically indicates missing API keys, invalid base URLs, or other
    configuration problems that prevent the healthcheck from running.
    """
    pass


class AiHealthcheckFailedError(RuntimeError):
    """
    Raised when AI healthcheck runs but fails.

    This indicates network errors, API quota issues, invalid responses,
    or other runtime failures during the healthcheck execution.
    """
    pass


class OpenAIConfigurationError(ValueError):
    """Raised when the OpenAI-compatible client is misconfigured."""


class OpenAIResponsesError(RuntimeError):
    """Raised when an OpenAI-compatible API returns an unusable response."""


class OpenAIHTTPStatusError(OpenAIResponsesError):
    """Raised when an HTTP API call returns a non-success status code."""

    def __init__(self, status_code: int, detail: str, route: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.route = route


class PromptTemplateError(FileNotFoundError):
    """Raised when a referenced prompt template file cannot be found."""


class PromptRenderError(ValueError):
    """Raised when a prompt template is missing required render values."""
