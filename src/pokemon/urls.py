from django.urls import path
from . import views


app_name = 'pokemon'
urlpatterns = [
    path('<str:name>/', views.poke_view, name='poke_view'),
    path('<str:name>/favorite', views.to_favorite, name='to_favorite'),
    path('pull_evolutions', views.pull_evolutions, name='pull_evolutions'),
]