from django.urls import path
from . import views
from .views import (
    ResourceListView,
    ToolListView,
    CourseListView,
    CorpusListView,
    ArticleListView,
    ThesisListView,
    MemoirListView,
    ResourceDetailView,
    ResourceCreateView,
    ResourceUpdateView,
    ResourceDeleteView,
    CourseCreateView,
    CorpusCreateView,
    ToolCreateView,
    resource_ajax_search,
)

app_name = 'resources'

urlpatterns = [
    # AJAX search endpoint
    path('api/search/', resource_ajax_search, name="ajax_search"),
    
    # Main resource listing
    path('', ResourceListView.as_view(), name="list"),
    
    # Detail views - note UUIDs instead of int for pk 
    path('details/<str:type>/<uuid:pk>/', ResourceDetailView.as_view(), name="resource-detail"),
    
    # Type-specific listings
    path('tools/', ToolListView.as_view(), name="tool_list"),
    path('courses/', CourseListView.as_view(), name="course_list"),
    path('corpus/', CorpusListView.as_view(), name="corpus_list"),
    path('articles/', ArticleListView.as_view(), name="article_list"),
    path('theses/', ThesisListView.as_view(), name="thesis_list"),
    path('memoirs/', MemoirListView.as_view(), name="memoir_list"),
    
    # Main create view (general)
    path('add/', ResourceCreateView.as_view(), name="create"),
    
    # Type-specific create views
    path('courses/add/', CourseCreateView.as_view(), name="course-create"),
    path('corpus/add/', CorpusCreateView.as_view(), name="corpus-create"),
    path('tools/add/', ToolCreateView.as_view(), name="tool-create"),
    path('articles/add/', ResourceCreateView.as_view(), name="article-create"),
    path('theses/add/', ResourceCreateView.as_view(), name="thesis-create"),
    path('memoirs/add/', ResourceCreateView.as_view(), name="memoir-create"),
    
    # Update and delete views
    path('update/<str:type>/<uuid:pk>/', ResourceUpdateView.as_view(), name="resource-update"),
    path('delete/<str:type>/<uuid:pk>/', ResourceDeleteView.as_view(), name="resource-delete"),
    
    # Type-specific detail views (backward compatibility)
    path('document/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'document'}, name="document_detail"),
    path('tool/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'tool'}, name="tool_detail"),
    path('course/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'course'}, name="course_detail"),
    path('article/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'article'}, name="article_detail"),
    path('thesis/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'thesis'}, name="thesis_detail"),
    path('memoir/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'memoir'}, name="memoir_detail"),
    path('corpus/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'corpus'}, name="corpus_detail"),
]
