from django.urls import path
from .views import (
    ProjectListView, ProjectDetailView, ProjectCreateView, 
    ProjectUpdateView, ProjectDeleteView, JoinProjectView, 
    LeaveProjectView, ProjectSearchView, AcceptMemberView,
    RejectMemberView, ProjectMembersView, RemoveMemberView, RespondToLeaveRequestView,
    RespondToRequestView, ProjectUserLookupView, InviteProjectMembersView,
    ProjectInvitationsView, AcceptProjectInvitationView, RejectProjectInvitationView,
    project_chatroom, project_chat_send, project_chat_delete_message,
    project_invitations_count_api,
)

app_name = 'projects'
urlpatterns = [
    path('', ProjectListView.as_view(), name='project_list'),
    path('<uuid:pk>/', ProjectDetailView.as_view(), name='project_detail'),
    path('new/', ProjectCreateView.as_view(), name='project_new'),
    path('<uuid:pk>/update/', ProjectUpdateView.as_view(), name='project_update'),
    path('<uuid:pk>/delete/', ProjectDeleteView.as_view(), name='project_delete'),
    path('<uuid:pk>/join/', JoinProjectView.as_view(), name='join_project'),
    path('<uuid:pk>/leave/', LeaveProjectView.as_view(), name='leave_project'),
    path('search/', ProjectSearchView.as_view(), name='project_search'),
    
    # Nouvelles URLs pour la gestion des membres
    path('<uuid:pk>/members/', ProjectMembersView.as_view(), name='project_members'),
    path('projects/<uuid:pk>/respond-leave/<uuid:member_id>/', RespondToLeaveRequestView.as_view(), name='respond_leave_request'),
    path('<uuid:pk>/members/<uuid:member_id>/accept/', AcceptMemberView.as_view(), name='accept_member'),
    path('<uuid:pk>/members/<uuid:member_id>/reject/', RejectMemberView.as_view(), name='reject_member'),
    path('<uuid:pk>/members/<uuid:member_id>/remove/', RemoveMemberView.as_view(), name='remove_member'),
    path('<uuid:pk>/request/<uuid:request_id>/respond/', RespondToRequestView.as_view(), name='respond_to_request'),
    path('<uuid:pk>/invite/search-users/', ProjectUserLookupView.as_view(), name='project_invite_user_search'),
    path('<uuid:pk>/invite/', InviteProjectMembersView.as_view(), name='project_invite'),
    path('invitations/', ProjectInvitationsView.as_view(), name='project_invitations'),
    path('invitations/count/', project_invitations_count_api, name='project_invitations_count_api'),
    path('invitation/<uuid:invitation_id>/accept/', AcceptProjectInvitationView.as_view(), name='project_invitation_accept'),
    path('invitation/<uuid:invitation_id>/reject/', RejectProjectInvitationView.as_view(), name='project_invitation_reject'),
    path('<uuid:pk>/chat/', project_chatroom, name='project_chatroom'),
    path('<uuid:pk>/chat/send/', project_chat_send, name='project_chat_send'),
    path('<uuid:pk>/chat/message/<uuid:message_id>/delete/', project_chat_delete_message, name='project_chat_delete_message'),
]

