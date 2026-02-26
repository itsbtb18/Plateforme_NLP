# chatbot/urls.py
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Pour charger l'interface HTML principale du chatbot
    path("", views.chatbot_interface, name="chatbot_interface"),

    # Point d'entrée principal pour toutes les interactions AJAX du chatbot depuis le JavaScript
    path("ask/", views.ask_bot, name="ask"),
    path("ask_bot/", views.ask_bot, name="ask_bot"),
    path("set_card_context/", views.set_card_context, name="set_card_context"),

    # Utilisé par chatbot_interface pour obtenir un session_id initial via FastAPI
    # Peut aussi être appelé explicitement par JS si un reset complet de session est nécessaire sans passer par 'ask_bot'
    path("start_new_session/", views.start_new_session, name="start_new_session"),
    
    # Get all chat history/sessions for current user
    path("history/", views.chat_history, name="chat_history"),
]
