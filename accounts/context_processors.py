# accounts/context_processors.py
from django.db.models import Q
from relations.models import Relation

def user_context(request):
    """
    Context processor pour ajouter les informations utilisateur
    dans tous les templates
    """
    context = {
        'notifications_non_lues': 0,
        'total_unread': 0,
    }
    
    if request.user.is_authenticated and hasattr(request.user, 'etudiant'):
        try:
            # Compter les demandes d'amitié non lues
            notifications_non_lues = Relation.objects.filter(
                destinataire=request.user.etudiant,
                statut='envoyee'
            ).count()
            
            context['notifications_non_lues'] = notifications_non_lues
            
            # Si vous avez un système de messages non lus
            # total_unread = Message.objects.filter(
            #     conversation__participants=request.user.etudiant,
            #     lu=False
            # ).exclude(expediteur=request.user.etudiant).count()
            # context['total_unread'] = total_unread
            
        except Exception as e:
            # En cas d'erreur, on garde les valeurs par défaut
            pass
    
    return context