import json
import logging
from types import SimpleNamespace

from config.logging import JsonFormatter


def test_json_formatter_uses_request_id_from_django_request():
    record = logging.LogRecord(
        name="django.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Conflict",
        args=(),
        exc_info=None,
    )
    record.request = SimpleNamespace(request_id="request-123")
    record.booking_id = 42

    payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] == "request-123"
    assert payload["booking_id"] == 42
