"""Helpers for interpreting S3-compatible storage errors."""

from collections.abc import Mapping
from typing import Any


_MISSING_OBJECT_CODES = frozenset(("NoSuchKey", "404", "AccessDenied"))


def is_missing_object_error(error: BaseException) -> bool:
    """Return whether an S3 get-object error means the object is absent.

    Supabase's S3-compatible endpoint can omit the S3 error code and expose
    only an HTTP 403/404 status for a missing object.  A coded 403/404 is not
    interchangeable with that response: authentication and bucket errors
    must continue to fail the release gate.
    """

    response: Any = getattr(error, "response", None) or {}
    if not isinstance(response, Mapping):
        return False

    error_details = response.get("Error") or {}
    if not isinstance(error_details, Mapping):
        error_details = {}
    code = str(error_details.get("Code", ""))
    if code in _MISSING_OBJECT_CODES:
        return True

    if code:
        return False

    metadata = response.get("ResponseMetadata") or {}
    if not isinstance(metadata, Mapping):
        return False
    return metadata.get("HTTPStatusCode") in (403, 404)
