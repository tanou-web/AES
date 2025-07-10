# messagerie/decorators.py
from functools import wraps
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from accounts.models import Etudiant
from .models import Conversation


def require_conversation_access(view_func):
    """
    Décorateur qui vérifie l'accès à une conversation
    """
    @wraps(view_func)
    def wrapper(request, conversation_id, *args, **kwargs):
        user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        if user_etudiant not in [conversation.participant1, conversation.participant2]:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Vous n\'avez pas accès à cette conversation.'
                }, status=403)
            else:
                messages.error(request, 'Vous n\'avez pas accès à cette conversation.')
                return redirect('messagerie:conversations')
        
        # Ajouter la conversation et l'utilisateur au contexte de la vue
        kwargs['user_etudiant'] = user_etudiant
        kwargs['conversation'] = conversation
        
        return view_func(request, conversation_id, *args, **kwargs)
    return wrapper


def require_message_access(view_func):
    """
    Décorateur qui vérifie l'accès à un message
    """
    @wraps(view_func)
    def wrapper(request, message_id, *args, **kwargs):
        from .models import Message
        user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
        message = get_object_or_404(Message, id=message_id)
        
        if not message.is_visible_for(user_etudiant):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Vous n\'avez pas accès à ce message.'
                }, status=403)
            else:
                return JsonResponse({
                    'error': 'Vous n\'avez pas accès à ce message.'
                }, status=403)
        
        # Ajouter le message et l'utilisateur au contexte de la vue
        kwargs['user_etudiant'] = user_etudiant
        kwargs['message'] = message
        
        return view_func(request, message_id, *args, **kwargs)
    return wrapper


# Tâches en arrière-plan (avec Celery si disponible)
def setup_periodic_tasks():
    """
    Configuration des tâches périodiques
    """
    try:
        from celery import Celery
        from celery.schedules import crontab
        
        app = Celery('social_network')
        
        # Nettoyer les anciens fichiers tous les jours à 2h du matin
        app.conf.beat_schedule = {
            'cleanup-old-files': {
                'task': 'messagerie.tasks.cleanup_old_files',
                'schedule': crontab(hour=2, minute=0),
            },
            # Nettoyer les notifications anciennes tous les dimanche
            'cleanup-old-notifications': {
                'task': 'relations.tasks.cleanup_old_notifications',
                'schedule': crontab(hour=3, minute=0, day_of_week=0),
            },
        }
        
    except ImportError:
        # Celery n'est pas installé, utiliser des tâches simples
        pass
