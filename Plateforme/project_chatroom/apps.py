from django.apps import AppConfig


class ProjectChatroomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'project_chatroom'
    verbose_name = 'Project Chatroom'

    def ready(self):
        import project_chatroom.signals
