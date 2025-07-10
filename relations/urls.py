from django.urls import path
from . import views

app_name = 'relations'

urlpatterns = [
    # Vues principales
    path('', views.relations_page, name='page'),
    path('notifications/', views.notifications_amitie, name='notifications'),
    path('statistiques/', views.statistiques_relations, name='statistiques'),
    
    # Actions sur les demandes
    path('envoyer/<int:destinataire_id>/', views.envoyer_demande, name='envoyer'),
    path('repondre/<int:relation_id>/<str:action>/', views.repondre_demande, name='repondre'),
    
    # Gestion des blocages
    path('bloquer/<int:etudiant_id>/', views.bloquer_utilisateur, name='bloquer'),
    path('debloquer/<int:relation_id>/', views.debloquer_utilisateur, name='debloquer'),
    
    # API AJAX
    path('ajax/envoyer-demande/', views.ajax_envoyer_demande, name='ajax_envoyer_demande'),
    path('ajax/suggestions/', views.ajax_suggestions, name='ajax_suggestions'),
    path('ajax/statistiques/', views.statistiques_relations, name='ajax_statistiques'),
]