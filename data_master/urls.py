from django.urls import path
from data_master import views

urlpatterns = [
    path('search/',                   views.search_view,  name='search'),
    path('prompt/',                   views.prompt_view,  name='prompt'),
    path('article/<slug:slug>/',      views.article_view, name='article'),
    path('article/<slug:slug>/json/', views.article_json, name='article_json'),
]