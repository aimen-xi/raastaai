"""One error shape for every failure: {"error": code, "message": text, "field": optional}."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, field: str | None = None, headers: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field
        self.headers = headers or {}

    def body(self) -> dict:
        b = {"error": self.code, "message": self.message}
        if self.field:
            b["field"] = self.field
        return b
