from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Pages principales
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Profil utilisateur
    path('profile/', views.profile_view, name='profile'),
    path('profile/<int:etudiant_id>/', views.view_profile, name='view_profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    
    # API et AJAX
    path('api/get-filieres/', views.get_filieres, name='get_filieres'),
    path('api/search-users/', views.search_users, name='search_users'),
    path('api/toggle-privacy/', views.toggle_privacy, name='toggle_privacy'),
    path('api/export-data/', views.export_data, name='export_data'),
    path('download-data/', views.download_profile_data, name='download_data'),
]