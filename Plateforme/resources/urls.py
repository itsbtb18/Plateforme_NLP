from django.urls import path
from . import views
from .views import (
    ResourceListView,
    ToolListView,  # Renamed from OutilListView
    CourseListView,  # Renamed from CoursListView
    CorpusListView,
    ArticleListView,
    ThesisListView,  # Renamed from TheseListView
    MemoirListView,  # Renamed from MemoireListView
    ResourceDetailView,
    ResourceCreateView,
    ResourceUpdateView,
    ResourceDeleteView,
    CourseCreateView,  
    CorpusCreateView,
    ToolCreateView,  # Renamed from OutilCreateView
)

app_name = 'resources'

urlpatterns = [
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
    
    # Create view
    path('add/', ResourceCreateView.as_view(), name="create"),
    path('update/<str:type>/<uuid:pk>/', ResourceUpdateView.as_view(), name="resource-update"),
    path('courses/add/', CourseCreateView.as_view(), name="course-create"),
    path('corpus/add/', CorpusCreateView.as_view(), name="corpus-create"),
    path('tools/add/', ToolCreateView.as_view(), name="tool-create"),
    
    path('delete/<str:type>/<uuid:pk>/', ResourceDeleteView.as_view(), name="resource-delete"),
    
    # Type-specific detail views
    path('document/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'document'}, name="document_detail"),
    path('tool/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'tool'}, name="tool_detail"),
    path('course/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'course'}, name="course_detail"),
    path('article/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'article'}, name="article_detail"),
    path('thesis/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'thesis'}, name="thesis_detail"),
    path('memoir/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'memoir'}, name="memoir_detail"),
    path('corpus/<uuid:pk>/', views.ResourceDetailView.as_view(), kwargs={'type': 'corpus'}, name="corpus_detail"),

    
]