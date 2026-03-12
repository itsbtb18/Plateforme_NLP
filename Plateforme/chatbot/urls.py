# chatbot/urls.py
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Main UI
    path("", views.chatbot_interface, name="chatbot_interface"),

    # Chat interaction (all modes go through this)
    path("ask/", views.ask_bot, name="ask"),
    path("ask_bot/", views.ask_bot, name="ask_bot"),
    path("set_card_context/", views.set_card_context, name="set_card_context"),

    # Session management
    path("sessions/create/", views.create_session, name="create_session"),
    path("sessions/", views.list_sessions, name="list_sessions"),
    path("sessions/rename/", views.rename_session, name="rename_session"),
    path("sessions/delete/", views.delete_session, name="delete_session"),
    path("sessions/<str:session_id>/history/", views.session_history, name="session_history"),
]
