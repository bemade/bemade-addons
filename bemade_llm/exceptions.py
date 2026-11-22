"""Typed errors raised by ``bemade.llm.stream.complete()``.

They derive from ``UserError`` so that an interactive caller shows them as a
plain message; background callers catch the subclass they care about.
"""

from odoo.exceptions import UserError


class BemadeLlmError(UserError):
    """Base class of every error raised by the LLM backend."""

    status = "error"


class LlmNotConfigured(BemadeLlmError):
    """The stream is unknown, archived, or has no active provider or model."""

    status = "not_configured"


class LlmCloudRefused(BemadeLlmError):
    """A local-only stream was pointed at a provider outside our infrastructure."""

    status = "cloud_refused"


class LlmTransportError(BemadeLlmError):
    """The server could not be reached, timed out or answered with an error."""

    status = "transport_error"


class LlmInvalidOutput(BemadeLlmError):
    """The answer is not JSON or does not follow the requested schema."""

    status = "invalid_output"


class LlmTruncated(LlmInvalidOutput):
    """The answer was cut off at the token limit (``finish_reason`` = "length")
    before it held valid JSON. Usually transient: retry, or raise max tokens."""

    status = "truncated"
