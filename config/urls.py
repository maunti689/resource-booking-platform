from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.views import LocalizedTokenObtainPairView, LocalizedTokenRefreshView, health, ready

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health),
    path("ready", ready),
    path("auth/token", LocalizedTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh", LocalizedTokenRefreshView.as_view(), name="token_refresh"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("", include("apps.organizations.urls")),
    path("", include("apps.resources.urls")),
    path("", include("apps.bookings.urls")),
]
