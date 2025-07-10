# messagerie/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from .models import Message, Conversation, MessageReaction
from .utils import invalidate_conversation_cache


@receiver(post_save, sender=Message)
def message_created(sender, instance, created, **kwargs):
    """Signal déclenché quand un message est créé ou modifié"""
    if created:
        # Invalider le cache des conversations pour les deux participants
        invalidate_conversation_cache(instance.sender)
        invalidate_conversation_cache(instance.receiver)
        
        # Mettre à jour la dernière activité de la conversation
        conversation = instance.conversation
        conversation.last_message_at = instance.created_at
        conversation.save(update_fields=['last_message_at'])
        
        # Invalider les compteurs de messages non lus
        cache_key_receiver = f'unread_count_{instance.receiver.id}'
        cache.delete(cache_key_receiver)


@receiver(post_save, sender=Message)
def message_read(sender, instance, **kwargs):
    """Signal déclenché quand un message est marqué comme lu"""
    if instance.is_read:
        # Invalider le cache de compteur de messages non lus
        cache_key = f'unread_count_{instance.receiver.id}'
        cache.delete(cache_key)


@receiver(post_delete, sender=Message)
def message_deleted(sender, instance, **kwargs):
    """Signal déclenché quand un message est supprimé"""
    # Invalider le cache des conversations
    invalidate_conversation_cache(instance.sender)
    invalidate_conversation_cache(instance.receiver)
    
    # Invalider les compteurs
    cache.delete(f'unread_count_{instance.receiver.id}')


@receiver(post_save, sender=Conversation)
def conversation_updated(sender, instance, **kwargs):
    """Signal déclenché quand une conversation est mise à jour"""
    # Invalider le cache pour les deux participants
    invalidate_conversation_cache(instance.participant1)
    invalidate_conversation_cache(instance.participant2)


# Fonctions utilitaires pour la gestion en temps réel
def get_online_users():
    """Récupère la liste des utilisateurs en ligne"""
    from django.contrib.auth.models import User
    
    online_users = []
    cutoff_time = timezone.now() - timezone.timedelta(minutes=5)
    
    # Chercher dans le cache d'abord
    users = User.objects.filter(is_active=True)
    for user in users:
        cache_key = f'user_activity_{user.id}'
        last_activity = cache.get(cache_key)
        
        if last_activity and last_activity > cutoff_time:
            online_users.append(user.id)
    
    return online_users


def is_user_online(user_id):
    """Vérifie si un utilisateur est en ligne"""
    cache_key = f'user_activity_{user_id}'
    last_activity = cache.get(cache_key)
    
    if last_activity:
        cutoff_time = timezone.now() - timezone.timedelta(minutes=5)
        return last_activity > cutoff_time
    
    return False