# accounts/middleware.py
# Créez ce fichier dans le dossier accounts/

from django.utils.deprecation import MiddlewareMixin
from django.db.models import Q
from relations.models import Relation

class NotificationMiddleware(MiddlewareMixin):
    """
    Middleware pour ajouter les compteurs de notifications
    dans le contexte de chaque requête
    """
    
    def process_request(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'etudiant'):
            try:
                # Compter les demandes d'amitié en attente
                notifications_count = Relation.objects.filter(
                    destinataire=request.user.etudiant,
                    statut='envoyee'
                ).count()
                
                # Ajouter au contexte de la requête
                request.notifications_non_lues = notifications_count
                
                # Si vous avez des messages non lus
                # request.total_unread = Message.objects.filter(...).count()
                request.total_unread = 0
                
            except Exception as e:
                # En cas d'erreur, mettre des valeurs par défaut
                request.notifications_non_lues = 0
                request.total_unread = 0
        else:
            request.notifications_non_lues = 0
            request.total_unread = 0