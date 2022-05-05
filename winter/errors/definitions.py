from typing import Any


class NotFoundError(Exception):
    def __init__(self, name: str):
        self.name = name


class ForbiddenError(Exception):
    def __init__(self, name: str, details: dict[str, Any] | None = None):
        self.name = name
        self.details = details


class InvalidRequestError(Exception):
    def __init__(self, details: dict[str, Any] | None = None):
        self.details = details


class InternalServerError(Exception):
    def __init__(self, details: dict[str, Any] | None = None):
        self.details = details
