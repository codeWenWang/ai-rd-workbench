import re
from collections.abc import Mapping
from typing import TypeAlias, cast


_REDACTED = "[REDACTED]"
_REDACTED_CYCLE = "[REDACTED_CYCLE]"
_TRUNCATED = "[TRUNCATED]"
_MAX_DETAIL_DEPTH = 8
_BEARER_RE = re.compile(
    r"\b(bearer\s+)(?P<quote>['\"]?)"
    r"(?P<secret>[^\s,;'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_API_KEY_RE = re.compile(
    r"\b(api[\s_-]*key\s*[:=]\s*)(?P<quote>['\"]?)"
    r"(?P<secret>[^\s,;'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_PROVIDER_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9._-])(?:sk-|pcsk_)[A-Za-z0-9][A-Za-z0-9._-]*",
    re.IGNORECASE,
)

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class DomainError(Exception):
    """Base error exposing only sanitized, JSON-safe public data.

    Detail mappings are normalized to JSON scalar, list, and string-keyed mapping
    values. Tuples become lists, unsupported objects become sanitized strings, and
    cyclic or excessively deep containers become explicit safe markers.
    """

    code = "domain_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self.message = _sanitize_text(message or self.code)
        self.details: dict[str, JsonValue] | None = (
            _sanitize_mapping(details) if details is not None else None
        )
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r})"


def _sanitize_text(value: str) -> str:
    sanitized = _BEARER_RE.sub(_replace_labeled_secret, value)
    sanitized = _API_KEY_RE.sub(_replace_labeled_secret, sanitized)
    return _PROVIDER_TOKEN_RE.sub(_REDACTED, sanitized)


def _replace_labeled_secret(match: re.Match[str]) -> str:
    quote = match.group("quote")
    return f"{match.group(1)}{quote}{_REDACTED}{quote}"


def _sanitize_mapping(value: Mapping[object, object]) -> dict[str, JsonValue]:
    sanitized = _sanitize_detail_value(value, seen=set(), depth=0)
    return cast(dict[str, JsonValue], sanitized)


def _sanitize_detail_value(
    value: object,
    *,
    seen: set[int],
    depth: int,
) -> JsonValue:
    if isinstance(value, str):
        return _sanitize_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (Mapping, list, tuple)):
        if depth >= _MAX_DETAIL_DEPTH:
            return _TRUNCATED
        identity = id(value)
        if identity in seen:
            return _REDACTED_CYCLE
        seen.add(identity)
        try:
            if isinstance(value, Mapping):
                return {
                    _sanitize_mapping_key(key): (
                        _REDACTED
                        if _is_sensitive_key(key)
                        else _sanitize_detail_value(
                            item,
                            seen=seen,
                            depth=depth + 1,
                        )
                    )
                    for key, item in value.items()
                }
            return [
                _sanitize_detail_value(item, seen=seen, depth=depth + 1)
                for item in value
            ]
        finally:
            seen.remove(identity)
    return _sanitize_unsupported_object(value)


def _sanitize_mapping_key(value: object) -> str:
    if isinstance(value, str):
        return _sanitize_text(value)
    return _sanitize_unsupported_object(value)


def _sanitize_unsupported_object(value: object) -> str:
    try:
        rendered = str(value)
    except Exception:
        rendered = f"<{type(value).__name__}>"
    return _sanitize_text(rendered)


def _is_sensitive_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[\s_-]+", "", value).casefold()
    return (
        normalized == "apikey"
        or normalized.endswith("apikey")
        or normalized == "token"
        or normalized.endswith("token")
        or normalized == "secret"
        or normalized.endswith("secret")
        or normalized == "secretkey"
        or normalized == "password"
        or normalized.endswith("password")
        or normalized.startswith("authorization")
        or normalized.endswith("authorization")
    )


class InvalidStateTransition(DomainError):
    code = "invalid_state_transition"


class ResourceNotFound(DomainError):
    code = "resource_not_found"


class ValidationError(DomainError):
    code = "validation_error"


class ExternalServiceError(DomainError):
    code = "external_service_error"


class IndexConsistencyError(DomainError):
    code = "index_consistency_error"
