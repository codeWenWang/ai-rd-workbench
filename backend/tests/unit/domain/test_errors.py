import json

from app.domain.errors import (
    DomainError,
    ExternalServiceError,
    IndexConsistencyError,
    InvalidStateTransition,
    ResourceNotFound,
    ValidationError,
)


def test_domain_errors_expose_stable_codes() -> None:
    assert DomainError.code == "domain_error"
    assert InvalidStateTransition.code == "invalid_state_transition"
    assert ResourceNotFound.code == "resource_not_found"
    assert ValidationError.code == "validation_error"
    assert ExternalServiceError.code == "external_service_error"
    assert IndexConsistencyError.code == "index_consistency_error"


def test_error_repr_does_not_expose_message_or_details() -> None:
    secret = "sk-do-not-leak"
    error = ExternalServiceError(
        f"provider rejected {secret}",
        details={"api_key": secret},
    )

    assert secret not in repr(error)
    assert repr(error) == "ExternalServiceError(code='external_service_error')"


def test_error_sanitizes_provider_tokens_in_public_message() -> None:
    dashscope_secret = "sk-review-secret"
    pinecone_secret = "pcsk_review_secret"
    error = ExternalServiceError(
        "embedding request failed with "
        f"{dashscope_secret}; Pinecone fallback {pinecone_secret} also failed"
    )

    public_values = [str(error), error.message, repr(error), repr(error.__dict__)]
    for public_value in public_values:
        assert dashscope_secret not in public_value
        assert pinecone_secret not in public_value

    assert "embedding request failed" in str(error)
    assert "Pinecone fallback" in str(error)
    assert "[REDACTED]" in str(error)


def test_error_recursively_sanitizes_labeled_secrets_in_details() -> None:
    secrets = {
        "mapping": "plain-mapping-secret",
        "equals": "plain-equals-secret",
        "colon": "plain-colon-secret",
        "bearer": "plain-bearer-secret",
        "token": "sk-nested-secret",
        "pinecone": "pcsk_nested_secret",
    }
    error = ExternalServiceError(
        "provider unavailable; authorization: bearer plain-message-secret",
        details={
            "api_key": secrets["mapping"],
            "attempts": [
                f"api_key={secrets['equals']}",
                (
                    f"api-key: {secrets['colon']}",
                    {"header": f"Authorization: Bearer {secrets['bearer']}"},
                ),
            ],
            "tokens": {
                "dashscope": secrets["token"],
                "pinecone": secrets["pinecone"],
            },
            "context": "retry after 5 seconds",
        },
    )

    exposed = " ".join(
        [str(error), repr(error), error.message, repr(error.details), str(error.args)]
    )
    for secret in [*secrets.values(), "plain-message-secret"]:
        assert secret not in exposed

    assert error.details is not None
    assert error.details["context"] == "retry after 5 seconds"
    assert "retry after 5 seconds" in exposed
    assert exposed.count("[REDACTED]") >= 7


def test_error_sanitizes_standalone_bearer_values_case_insensitively() -> None:
    message_secret = "standalone-message-token"
    detail_secret = "standalone-detail-token"
    error = ExternalServiceError(
        f"request denied by bEaReR {message_secret}; retry is allowed",
        details={
            "events": [
                f"upstream returned BEARER {detail_secret} before fallback"
            ],
            "context": "fallback remains available",
        },
    )

    exposed = " ".join(
        [
            str(error),
            repr(error),
            error.message,
            str(error.args),
            repr(error.details),
        ]
    )
    assert message_secret not in exposed
    assert detail_secret not in exposed
    assert "request denied" in exposed
    assert "retry is allowed" in exposed
    assert "fallback remains available" in exposed


def test_sensitive_mapping_keys_redact_entire_container_values() -> None:
    secrets = [
        "list-child-value",
        "nested-child-value",
        "client-secret-primary",
        "tuple-password-value",
        "nested-password-value",
        "authorization-child-value",
    ]
    error = ExternalServiceError(
        "credential refresh failed; retry remains available",
        details={
            "credentials": {
                "access-token": [
                    secrets[0],
                    {"child": secrets[1]},
                ],
                "client_secret": {"primary": secrets[2]},
                "redis-password": (
                    secrets[3],
                    {"nested": secrets[4]},
                ),
                "authorization_header": {"raw": secrets[5]},
            },
            "context": "rotate credentials and retry after 5 seconds",
        },
    )

    exposed = " ".join(
        [
            str(error),
            repr(error),
            error.message,
            str(error.args),
            repr(error.details),
            repr(error.__dict__),
        ]
    )
    for secret in secrets:
        assert secret not in exposed

    assert error.details is not None
    credentials = error.details["credentials"]
    assert isinstance(credentials, dict)
    assert credentials == {
        "access-token": "[REDACTED]",
        "client_secret": "[REDACTED]",
        "redis-password": "[REDACTED]",
        "authorization_header": "[REDACTED]",
    }
    assert "rotate credentials and retry after 5 seconds" in exposed


def test_error_sanitizes_api_key_labels_with_common_separators() -> None:
    secrets = [
        "space-separated-value",
        "underscore-colon-value",
        "hyphen-equals-value",
    ]
    error = ExternalServiceError(
        f"provider rejected API key = {secrets[0]}; retry remains available",
        details={
            "events": [
                f"api_key: {secrets[1]}",
                f"api-key={secrets[2]}",
            ]
        },
    )

    exposed = _exposed_error_text(error)
    for secret in secrets:
        assert secret not in exposed
    assert "provider rejected" in exposed
    assert "retry remains available" in exposed


def test_error_details_convert_exception_objects_to_sanitized_json_strings() -> None:
    secret = "exception-object-secret"
    error = ExternalServiceError(
        "provider failed but retry remains available",
        details={
            "cause": RuntimeError(f"upstream API key = {secret}"),
            "attempt": 2,
        },
    )

    exposed = _exposed_error_text(error)
    assert secret not in exposed
    assert "upstream API key = [REDACTED]" in exposed
    assert error.details is not None
    assert isinstance(error.details["cause"], str)
    assert json.loads(json.dumps(error.details)) == error.details


def test_error_details_replace_mapping_and_list_cycles_with_safe_markers() -> None:
    cyclic_mapping: dict[str, object] = {"context": "mapping context retained"}
    cyclic_mapping["self"] = cyclic_mapping
    cyclic_list: list[object] = ["list context retained"]
    cyclic_list.append(cyclic_list)

    error = ExternalServiceError(
        "cyclic details received; request can continue",
        details={"mapping": cyclic_mapping, "items": cyclic_list},
    )

    exposed = _exposed_error_text(error)
    assert "[REDACTED_CYCLE]" in exposed
    assert "mapping context retained" in exposed
    assert "list context retained" in exposed
    assert json.loads(json.dumps(error.details)) == error.details


def test_error_details_truncate_excessive_nesting_without_reaching_secret() -> None:
    secret = "sk-too-deep-to-retain"
    nested: dict[str, object] = {"API key": secret}
    for _ in range(20):
        nested = {"child": nested}

    error = ExternalServiceError(
        "deep details received; retry remains available",
        details={"context": "outer context retained", "nested": nested},
    )

    exposed = _exposed_error_text(error)
    assert secret not in exposed
    assert "[TRUNCATED]" in exposed
    assert "outer context retained" in exposed
    assert json.loads(json.dumps(error.details)) == error.details


def _exposed_error_text(error: DomainError) -> str:
    return " ".join(
        [
            str(error),
            repr(error),
            error.message,
            str(error.args),
            repr(error.details),
            repr(error.__dict__),
        ]
    )
