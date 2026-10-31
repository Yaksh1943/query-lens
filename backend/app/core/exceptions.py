"""
Custom domain exceptions for QueryLens.

Defines a structured exception hierarchy with error codes and HTTP status codes
for consistent, predictable API error responses.
"""


class QueryLensError(Exception):
    """Base exception for all domain-level QueryLens errors."""

    def __init__(self, message: str, code: str = "QUERYLENS_ERROR", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class DatabaseConnectionNotFoundError(QueryLensError):
    """Raised when a requested database connection is not found."""

    def __init__(self, connection_id: int) -> None:
        super().__init__(
            message=f"No database connection found for id {connection_id}.",
            code="CONNECTION_NOT_FOUND",
            status_code=404,
        )


class QueryHistoryNotFoundError(QueryLensError):
    """Raised when a trace_id is not found in query history."""

    def __init__(self, trace_id: int) -> None:
        super().__init__(
            message=f"No query history found for trace_id {trace_id}.",
            code="TRACE_NOT_FOUND",
            status_code=404,
        )


class InvalidQueryRequestError(QueryLensError):
    """Raised when request parameters are missing or invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_REQUEST", status_code=400)
