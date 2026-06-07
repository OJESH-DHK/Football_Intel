from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health(_request):
    # Liveness probe — no DB/Redis touch so it stays green during dep restarts.
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("telegram/", include("apps.bot.urls")),
    path("api/v1/", include("apps.articles.urls")),
    path("dashboard/", include("apps.matches.urls")),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
