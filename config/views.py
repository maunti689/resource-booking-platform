import logging

from django.core.cache import cache
from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from redis.exceptions import RedisError
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

logger = logging.getLogger(__name__)


@extend_schema_view(post=extend_schema(summary="Получить пару JWT-токенов", tags=["Авторизация"]))
class LocalizedTokenObtainPairView(TokenObtainPairView):
    pass


@extend_schema_view(post=extend_schema(summary="Обновить JWT-токен", tags=["Авторизация"]))
class LocalizedTokenRefreshView(TokenRefreshView):
    pass


class HealthStatusSerializer(serializers.Serializer):
    status = serializers.CharField()


@extend_schema(
    operation_id="health",
    summary="Проверить процесс приложения",
    tags=["Система"],
    responses=HealthStatusSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return JsonResponse({"status": "ok"})


@extend_schema(
    operation_id="readiness",
    summary="Проверить готовность базы данных и Redis",
    tags=["Система"],
    responses=HealthStatusSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache.set("readiness-probe", "ok", timeout=5)
        if cache.get("readiness-probe") != "ok":
            raise RuntimeError("Проверка готовности кэша завершилась ошибкой")
    except (ConnectionError, DatabaseError, RedisError, RuntimeError, TimeoutError):
        logger.exception("Проверка готовности завершилась ошибкой")
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready"})
