from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler

from config.logging import request_id_context


class ConflictError(APIException):
    status_code = 409
    default_code = "conflict"
    default_detail = "Операция конфликтует с текущим состоянием"


class DomainValidationError(APIException):
    status_code = 422
    default_code = "domain_validation_failed"
    default_detail = "Запрос нарушает бизнес-правило"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    code = getattr(exc, "default_code", "request_failed")
    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        details = {}
    else:
        message = "Запрос не прошёл проверку"
        details = detail
    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id_context.get(),
        }
    }
    return response
