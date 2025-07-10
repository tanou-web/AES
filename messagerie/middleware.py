# messagerie/middleware.py
from django.core.cache import cache
from django.utils import timezone


class UserActivityMiddleware:
    """Middleware pour tracker l'activité des utilisateurs"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code à exécuter pour chaque requête avant la vue
        if request.user.is_authenticated:
            # Mettre à jour en cache pour éviter trop d'écritures en DB
            cache_key = f'user_activity_{request.user.id}'
            cache.set(cache_key, timezone.now(), timeout=300)  # 5 minutes
        
        response = self.get_response(request)
        
        # Code à exécuter pour chaque requête/réponse après la vue
        return response