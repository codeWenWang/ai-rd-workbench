from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum


def serialize(value):
    data = asdict(value)
    return {key: _value(item) for key, item in data.items()}


def _value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list):
        return [_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _value(item) for key, item in value.items()}
    return value
