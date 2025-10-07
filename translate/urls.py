from django.urls import path
from translate.views import switch_language 
from . import views

app_name = "translate"
urlpatterns = [
  
  path('switch-language/', views.switch_language, name='switch_language'),

]
