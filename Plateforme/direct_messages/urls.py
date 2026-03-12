from django.urls import path

from . import views

app_name = "direct_messages"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("start/<uuid:user_id>/", views.start_conversation, name="start_conversation"),
    path("group/create/", views.create_group, name="create_group"),
    path("thread/<uuid:conversation_id>/", views.thread, name="thread"),
    path("conversation/<uuid:conversation_id>/accept/", views.accept_conversation, name="accept_conversation"),
    path("conversation/<uuid:conversation_id>/delete/", views.delete_conversation, name="delete_conversation"),
    path("conversation/<uuid:conversation_id>/mute/", views.set_mute, name="set_mute"),
    path("group/<uuid:conversation_id>/edit/", views.update_group_info, name="update_group_info"),
    path("group/<uuid:conversation_id>/add-member/", views.add_group_member, name="add_group_member"),
    path("group/<uuid:conversation_id>/remove-member/", views.remove_group_member, name="remove_group_member"),
    path("group/<uuid:conversation_id>/leave/", views.leave_group, name="leave_group"),
    path("thread/<uuid:conversation_id>/mark-read/", views.mark_as_read, name="mark_as_read"),
    path("unread-count/", views.unread_count, name="unread_count"),
    path("unread-map/", views.unread_map, name="unread_map"),
]
