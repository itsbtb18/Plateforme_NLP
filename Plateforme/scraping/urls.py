from django.urls import path
from . import views

app_name = "scraping"

urlpatterns = [
    path("metrics/", views.metrics_view, name="metrics"),
    path("", views.dashboard, name="dashboard"),
    path("run/<str:category>/", views.run_scraper, name="run_scraper"),
    path("runs/recent/", views.recent_runs, name="recent_runs"),
    path(
        "runs/<uuid:run_id>/rerun/", views.rerun_scraping_run, name="rerun_scraping_run"
    ),
    path("duplicates/", views.duplicates_preview, name="duplicates_preview"),
    path(
        "run-custom/<uuid:source_id>/",
        views.run_custom_source,
        name="run_custom_source",
    ),
    path("sources/<uuid:source_id>/test/", views.test_source, name="test_source"),
    path(
        "sources/test-status/<str:job_id>/",
        views.test_source_status,
        name="test_source_status",
    ),
    path("status/<uuid:run_id>/", views.run_scraper_status, name="run_scraper_status"),
    path("task-status/<uuid:run_id>/", views.task_status, name="task_status"),
    path("trends/", views.trends, name="trends"),
    path("analytics/", views.analytics, name="analytics"),
    path(
        "analytics/skip-reasons/",
        views.skip_reason_analytics,
        name="skip_reason_analytics",
    ),
    path(
        "analytics/source-health/",
        views.source_health_summary,
        name="source_health_summary",
    ),
    path("sources/add/", views.add_custom_source, name="add_custom_source"),
    path(
        "sources/delete/<uuid:source_id>/",
        views.delete_custom_source,
        name="delete_custom_source",
    ),
    path("sources/list/", views.list_custom_sources, name="list_custom_sources"),
]
