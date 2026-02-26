from django.urls import path
from . import views

app_name = "scraping"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("run/<str:category>/", views.run_scraper, name="run_scraper"),
]
