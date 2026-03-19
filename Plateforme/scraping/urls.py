from django.urls import path
from . import views

app_name = "scraping"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("run/<str:category>/", views.run_scraper, name="run_scraper"),
    path("run-custom/<uuid:source_id>/", views.run_custom_source, name="run_custom_source"),
    path("status/<uuid:run_id>/", views.task_status, name="task_status"),
    path("trends/", views.trends, name="trends"),
    path("sources/add/", views.add_custom_source, name="add_custom_source"),
    path("sources/delete/<uuid:source_id>/", views.delete_custom_source, name="delete_custom_source"),
    path("sources/list/", views.list_custom_sources, name="list_custom_sources"),
]
