from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.live_matches, name="live"),
    path("fixtures/", views.fixtures, name="fixtures"),
    path("competitions/", views.competitions, name="competitions"),
    path("match/<int:pk>/", views.match_detail, name="match_detail"),
]
