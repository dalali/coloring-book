"""Consistent error envelope for the API (architecture §4.4)."""
from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    """HTTPException that serializes to the standard error envelope.

    The exception handler in main.py renders ``detail`` as
    ``{"error": {"code": ..., "message": ...}}``.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
        self.code = code
        self.message = message


# Convenience constructors for the documented error cases (architecture §4.4).
def unsupported_type(message: str = "Unsupported image type. Use JPG, PNG, or WebP.") -> ApiError:
    return ApiError(400, "UNSUPPORTED_TYPE", message)


def file_too_large(message: str) -> ApiError:
    return ApiError(400, "FILE_TOO_LARGE", message)


def empty_prompt(message: str = "Please describe what you'd like to color.") -> ApiError:
    return ApiError(400, "EMPTY_PROMPT", message)


def content_policy(message: str = "That prompt was rejected by the image generator.") -> ApiError:
    return ApiError(400, "CONTENT_POLICY", message)


def unreadable_image(message: str = "That image could not be read.") -> ApiError:
    return ApiError(422, "UNREADABLE_IMAGE", message)


def generation_unavailable(message: str = "Image generation is temporarily unavailable.") -> ApiError:
    return ApiError(502, "GENERATION_UNAVAILABLE", message)


def text_flow_disabled(message: str = "Text-to-image is not configured on this server.") -> ApiError:
    return ApiError(503, "TEXT_FLOW_DISABLED", message)
