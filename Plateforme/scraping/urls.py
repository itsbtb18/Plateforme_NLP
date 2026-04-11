from django.urls import path

from . import views_root as views

app_name = "scraping"

urlpatterns = [
    # Main pages
    path("", views.scraping_dashboard, name="dashboard"),
    path("dashboard/", views.scraping_dashboard, name="scraping_dashboard"),
    path("results/", views.scraping_results, name="results"),
    path("results/", views.scraping_results, name="scraping_results"),
    path(
        "results/<int:item_id>/",
        views.scraping_result_detail,
        name="result_detail",
    ),
    path(
        "results/<uuid:item_id>/",
        views.scraping_result_detail,
        name="result_detail",
    ),
    path(
        "results/<uuid:item_id>/",
        views.scraping_result_detail,
        name="scraping_result_detail",
    ),
    path("sources/", views.scraping_sources_page, name="sources"),
    path("sources/", views.scraping_sources_page, name="scraping_sources"),
    path("analytics/", views.scraping_analytics_page, name="scraping_analytics"),
    path("analytics/", views.scraping_analytics_page, name="analytics"),
    path("settings/", views.scraping_settings_page, name="settings"),
    path("settings/", views.scraping_settings_page, name="scraping_settings"),
    # Notifications
    path(
        "notifications/mark-read/",
        views.mark_notifications_read,
        name="mark_notifications_read",
    ),
    # API endpoints (normalized names)
    path(
        "api/translate-field/",
        views.api_translate_field,
        name="api_translate_field",
    ),
    path(
        "api/save-draft/<int:item_id>/",
        views.api_save_draft,
        name="api_save_draft",
    ),
    path(
        "api/save-draft/<uuid:item_id>/",
        views.api_save_draft,
        name="api_save_draft",
    ),
    path(
        "api/reject/<int:item_id>/",
        views.api_reject_item,
        name="api_reject_item",
    ),
    path(
        "api/reject/<uuid:item_id>/",
        views.api_reject_item,
        name="api_reject_item",
    ),
    path(
        "api/stats/<str:category>/",
        views.api_category_stats,
        name="api_category_stats",
    ),
    # Existing routes (kept for backward compatibility)
    path("metrics/", views.scraping_metrics_view, name="metrics"),
    path(
        "results/validate/<uuid:item_id>/",
        views.scraping_result_validate,
        name="scraping_result_validate",
    ),
    path(
        "results/delete/<uuid:item_id>/",
        views.scraping_result_delete,
        name="scraping_result_delete",
    ),
    path(
        "results/bulk-action/",
        views.scraping_results_bulk_action,
        name="scraping_results_bulk_action",
    ),
    path("run/<str:category>/", views.run_scraper, name="run_scraper"),
    path(
        "stop/<uuid:run_id>/",
        views.stop_scraping_run,
        name="stop_scraping_run",
    ),
    path(
        "api/stats/<str:category>/",
        views.category_stats,
        name="category_stats",
    ),
    path(
        "api/quick-stats/",
        views.quick_stats,
        name="quick_stats",
    ),
    path(
        "api/prompts/add/",
        views.add_prompt_api,
        name="add_prompt_api",
    ),
    path(
        "api/prompts/<int:query_id>/toggle/",
        views.toggle_prompt_api,
        name="toggle_prompt_api",
    ),
    path(
        "api/translate-field/",
        views.translate_field_api,
        name="translate_field_api",
    ),
    path(
        "api/save-draft/<uuid:item_id>/",
        views.save_draft_api,
        name="save_draft_api",
    ),
    path(
        "api/reject/<uuid:item_id>/",
        views.reject_scraping_item_api,
        name="reject_scraping_item_api",
    ),
    path(
        "api/validate-source/",
        views.validate_source,
        name="validate_source",
    ),
    path(
        "api/validate-source/<uuid:source_id>/",
        views.validate_source,
        name="validate_source_by_id",
    ),
    path(
        "api/validate-source-status/<str:task_id>/",
        views.validate_source_status,
        name="validate_source_status",
    ),
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
        "sources/test-connection/",
        views.test_source_connection,
        name="test_source_connection",
    ),
    path(
        "sources/<uuid:source_id>/health/",
        views.source_health_detail,
        name="source_health_detail",
    ),
    path(
        "sources/<uuid:source_id>/toggle/",
        views.toggle_custom_source,
        name="toggle_custom_source",
    ),
    path(
        "sources/delete/<uuid:source_id>/",
        views.delete_custom_source,
        name="delete_custom_source",
    ),
    path("sources/list/", views.list_custom_sources, name="list_custom_sources"),
]
