from django.urls import path
from . import views

app_name = 'institutions'

urlpatterns = [
    path('', views.InstitutionListView.as_view(), name='institution_list'),
    path('<uuid:pk>/', views.InstitutionDetailView.as_view(), name='institution_detail'),
    path('add/', views.InstitutionCreateView.as_view(), name='institution_create'),
    path('<uuid:pk>/edit/', views.InstitutionUpdateView.as_view(), name='institution_update'),
    path('<uuid:pk>/delete/', views.InstitutionDeleteView.as_view(), name='institution_delete'),
]