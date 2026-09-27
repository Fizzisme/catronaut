"""LLM client errors, classified by whether a retry can help (book guide ch05 §5.1.5)."""

import openai


class LLMError(Exception):
    """Base class for every error raised by the LLM client."""


class LLMRequestError(LLMError):
    """The server rejected the request; retrying the same request cannot succeed."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMUnavailableError(LLMError):
    """Every attempt failed with a retryable error; the cause is the last failure."""

    def __init__(self, message: str, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


class LLMStreamInterrupted(LLMError):
    """The stream broke after events were already delivered, so it is not retried silently."""


def is_retryable(exc: openai.APIError) -> bool:
    """429, 5xx and connection failures (resets and timeouts included) are retryable."""
    if isinstance(exc, openai.APIConnectionError):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False
