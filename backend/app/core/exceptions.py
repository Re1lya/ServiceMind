"""Custom exception definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BusinessException(Exception):
    """Base exception for standardized business-level failures."""

    message: str
    code: int = 10000
    detail: Any | None = None
    status_code: int = 400
    extra: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class ValidationException(BusinessException):
    """Exception raised for invalid business inputs."""

    def __init__(self, message: str = "validation failed", detail: Any | None = None) -> None:
        super().__init__(message=message, code=10001, detail=detail, status_code=422)


class ExternalServiceException(BusinessException):
    """Exception raised when an upstream dependency is unavailable."""

    def __init__(self, message: str = "external service unavailable", detail: Any | None = None) -> None:
        super().__init__(message=message, code=20001, detail=detail, status_code=503)


class NotFoundException(BusinessException):
    """Exception raised when a requested resource does not exist."""

    def __init__(self, message: str = "resource not found", detail: Any | None = None) -> None:
        super().__init__(message=message, code=40404, detail=detail, status_code=404)
