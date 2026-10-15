class UnitlabError(Exception):
    """Base class for exceptions."""

    def __init__(
        self,
        message: str,
        detail: Exception | None = None,
        code: str = "",
    ):
        super().__init__(message, detail)
        self.message = message
        self.detail = detail
        self.code = code

    def __str__(self) -> str:
        return self.message


class AuthenticationError(UnitlabError):
    """Raised when an API key fails authentication."""


class NetworkError(UnitlabError):
    """Raised when an HTTP error occurs."""


class ValidationError(NetworkError):
    """Raised when the API rejects input with a 400 response."""


class NotFoundError(NetworkError):
    """Raised when the requested resource is not found."""


class ConflictError(NetworkError):
    """Raised when the API answers 409 because the resource is in a conflicting state.

    Subclasses NetworkError so callers that already catch NetworkError keep
    working; ``code`` tells the cases apart (``release_in_progress`` for a
    second create while one is being prepared, ``release_not_ready`` for a
    download before the Release is ready).
    """


class SubscriptionError(NetworkError):
    """Raised when a subscription error occurs."""


class PermissionDeniedError(NetworkError):
    """Raised when the authenticated API key cannot perform an action."""


class TimeoutError(UnitlabError):
    """Raised when a request times out."""


RequestTimeoutError = TimeoutError


class ProcessingTimeoutError(TimeoutError):
    """Raised when server-side processing is still running at the deadline."""

    def __init__(self, message: str, status=None, detail: Exception | None = None):
        super().__init__(message, detail)
        self.status = status


class AnnotationImportError(UnitlabError):
    """Raised when an annotation import cannot be written as previewed.

    ``rows`` lists the blocked annotations (``key``, ``external_key``,
    ``media_key``, ``reason``) and ``issues`` the file-level problems
    (``row``, ``reason``) of the preview the server checked. ``batch_id``
    is the import batch. Nothing was written when this is raised.
    """

    def __init__(
        self,
        message: str,
        detail: Exception | None = None,
        code: str = "annotation_import_failed",
        *,
        rows: list | None = None,
        issues: list | None = None,
        batch_id: str | None = None,
    ):
        super().__init__(message, detail, code)
        self.rows = rows or []
        self.issues = issues or []
        self.batch_id = batch_id

    def __str__(self) -> str:
        # Show the first reasons inline: the server's commit message alone
        # ("Resolve blocked records ...") does not say which rows.
        lines = [self.message]
        reasons = [
            f"{row.get('external_key') or row.get('key')}: {row.get('reason')}"
            for row in self.rows
        ] + [f"{issue.get('row')}: {issue.get('reason')}" for issue in self.issues]
        lines += [f"  - {reason}" for reason in reasons[:5]]
        if len(reasons) > 5:
            lines.append(f"  ... and {len(reasons) - 5} more (see .rows / .issues)")
        return "\n".join(lines)


class AmbiguousUploadCompletionError(NetworkError):
    """Raised when multipart completion may have succeeded server-side."""
