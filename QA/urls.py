from django.urls import path
from . import views

app_name = 'QA'

urlpatterns = [
    path('', views.qa_home, name='qa_list'),
    path('ask/', views.ask_question, name='ask_question'),
    path('question/<int:pk>/', views.question_detail, name='question_detail'),
    path('search/', views.search_questions, name='search'),
    path('feed/', views.feed, name='feed'),
    path('post/create/', views.create_post, name='create_post'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
    path('post/<uuid:post_id>/comment/', views.add_comment, name='add_comment'),
    path('post/<uuid:post_id>/like/', views.like_post, name='like_post'),
    path('comment/<uuid:comment_id>/like/', views.like_comment, name='like_comment'),
    path('post/<uuid:post_id>/delete/', views.delete_post, name='delete_post'),
    path('comment/<uuid:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('post/<uuid:post_id>/edit/', views.edit_post, name='edit_post'),
    path('comment/<uuid:comment_id>/edit/', views.edit_comment, name='edit_comment'),
]
