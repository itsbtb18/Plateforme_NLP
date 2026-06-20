from django.urls import path
from .views import HomePageView, OpportunitiesPageView
from . import views

app_name = "pages"
urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("opportunities/", OpportunitiesPageView.as_view(), name="opportunities"),
    path("opportunities/create/", views.create_opportunity, name="create_opportunity"),
    # Main admin views
    path("admin/contact", views.contact_view, name="contact"),
    path("admin/", views.admin_contact_list, name="admin_contact_list"),
    path("admin/<int:pk>/", views.admin_contact_detail, name="admin_contact_detail"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/users/", views.admin_users, name="admin_users"),
    path("admin/publications/", views.admin_publications, name="admin_publications"),
    path("admin/news/", views.admin_news, name="admin_news"),
    path("admin/news/create/", views.admin_news_form, name="admin_news_create"),
    path("admin/news/<int:publication_id>/edit/", views.admin_news_form, name="admin_news_edit"),
    path("admin/publications", views.admin_publications_api, name="admin_publications_api"),
    path(
        "admin/publications/<int:publication_id>",
        views.admin_publications_detail_api,
        name="admin_publications_detail_api",
    ),
    path("admin/corpora/", views.admin_corpora, name="admin_corpora"),
    path("admin/tools/", views.admin_tools, name="admin_tools"),
    path("admin/projects/", views.admin_projects, name="admin_projects"),
    path("admin/courses/", views.admin_courses, name="admin_courses"),
    path("admin/opportunities/", views.admin_opportunities, name="admin_opportunities"),
    path(
        "admin/opportunities/<uuid:pk>/edit/",
        views.admin_opportunity_update,
        name="admin_opportunity_update",
    ),
    path(
        "admin/opportunities/<uuid:pk>/approve/",
        views.admin_opportunity_approve,
        name="admin_opportunity_approve",
    ),
    path(
        "admin/opportunities/<uuid:pk>/reject/",
        views.admin_opportunity_reject,
        name="admin_opportunity_reject",
    ),
    path("admin/forum/", views.admin_forum, name="admin_forum"),
    path("admin/institutions/", views.admin_institutions, name="admin_institutions"),
    path("admin/feed/", views.admin_feed, name="admin_feed"),
    path(
        "admin/feed/<uuid:post_id>/approve/",
        views.admin_feed_approve,
        name="admin_feed_approve",
    ),
    path(
        "admin/feed/<uuid:post_id>/delete/",
        views.admin_feed_delete,
        name="admin_feed_delete",
    ),
    path(
        "admin/feed/<uuid:post_id>/view/", views.admin_feed_view, name="admin_feed_view"
    ),
    path("admin/calls/", views.admin_calls, name="admin_calls"),
    path("admin/statistics/", views.admin_statistics, name="admin_statistics"),
    path("admin/settings/", views.admin_settings, name="admin_settings"),
    path("admin/security/", views.admin_security, name="admin_security"),
    path(
        "admin/security/activity-data/",
        views.admin_security_activity_api,
        name="admin_security_activity_api",
    ),
    # User management
    path(
        "admin/users/<uuid:user_id>/edit/",
        views.admin_user_edit,
        name="admin_user_edit",
    ),
    path("admin/users/new/", views.admin_users_new, name="admin_users_new"),
    path(
        "admin/users/<uuid:user_id>/delete/",
        views.admin_user_delete,
        name="admin_user_delete",
    ),
    path(
        "admin/users/<uuid:user_id>/activate/",
        views.admin_user_activate,
        name="admin_user_activate",
    ),
    path(
        "admin/users/<uuid:user_id>/block/",
        views.admin_user_block,
        name="admin_user_block",
    ),
    path(
        "admin/users/<uuid:user_id>/history/",
        views.admin_user_history,
        name="admin_user_history",
    ),
    path(
        "admin/users/<uuid:user_id>/status/<str:status>/",
        views.admin_user_status,
        name="admin_user_status",
    ),
    # Approval workflow
    path(
        "admin/view/<str:model_type>/<uuid:pk>/",
        views.admin_view_item,
        name="admin_view_item",
    ),
    path(
        "admin/approve/<str:model_type>/<uuid:pk>/",
        views.admin_approve_item,
        name="admin_approve_item",
    ),
    path(
        "admin/reject/corpus/<uuid:pk>/",
        views.admin_reject_item,
        {"model_type": "corpus"},
        name="admin_reject_corpus",
    ),
    path(
        "admin/reject/publication/<uuid:pk>/",
        views.admin_reject_item,
        {"model_type": "publication"},
        name="admin_reject_publication",
    ),
    path(
        "admin/reject/project/<uuid:pk>/",
        views.admin_reject_item,
        {"model_type": "project"},
        name="admin_reject_project",
    ),
    path(
        "admin/reject/tool/<uuid:pk>/",
        views.admin_reject_item,
        {"model_type": "tool"},
        name="admin_reject_tool",
    ),
    path(
        "admin/reject/forum/<uuid:pk>/",
        views.admin_reject_item,
        {"model_type": "forum"},
        name="admin_reject_forum",
    ),
    path(
        "admin/reject/feed/<uuid:pk>/",
        views.admin_reject_item,
        {"model_type": "news"},
        name="admin_reject_feed",
    ),
    path("publications", views.publications_list, name="publications_list"),
    path(
        "publications/<int:publication_id>",
        views.publication_detail,
        name="publication_detail",
    ),
    path(
        "publications/<int:publication_id>/convert-to-text/",
        views.publication_convert_to_text,
        name="publication-convert-to-text",
    ),
    path(
        "admin/reject/<str:model_type>/<uuid:pk>/",
        views.admin_reject_item,
        name="admin_reject_item",
    ),
    path(
        "admin/delete/<str:model_type>/<uuid:pk>/",
        views.admin_delete_item,
        name="admin_delete_item",
    ),
    path(
        "admin/review/<str:model_type>/<uuid:pk>/",
        views.admin_review_item_api,
        name="admin_review_item_api",
    ),
    path(
        "admin/review/<str:model_type>/<uuid:pk>/save/",
        views.admin_review_save_api,
        name="admin_review_save_api",
    ),
    # API endpoints
    path("admin/api/stats/", views.admin_api_stats, name="admin_api_stats"),
    path(
        "admin/api/recent_users/",
        views.admin_api_recent_users,
        name="admin_api_recent_users",
    ),
    path(
        "admin/api/recent_content/",
        views.admin_api_recent_content,
        name="admin_api_recent_content",
    ),
]
