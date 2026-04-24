from django.urls import path
from . import views

app_name = "translate"

urlpatterns = [
    # Language switcher (legacy)
    path("switch-language/", views.switch_language, name="switch_language"),

    # Translation / Summarization proxy API
    path("api/ts/translate/", views.api_translate, name="api_ts_translate"),
    path("api/ts/summarize/", views.api_summarize, name="api_ts_summarize"),
    path("api/ts/health/", views.api_ts_health, name="api_ts_health"),
]
