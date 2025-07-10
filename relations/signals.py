from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Relation, NotificationAmitie


@receiver(post_save, sender=Relation)
def handle_relation_status_change(sender, instance, created, **kwargs):
    """
    Gère les changements de statut des relations et crée les notifications appropriées
    """
    if created:
        # Nouvelle demande d'amitié créée
        if instance.statut == 'envoyee':
            NotificationAmitie.objects.get_or_create(
                destinataire=instance.destinataire,
                expediteur=instance.expediteur,
                relation=instance,
                type_notification='demande_recue',
                defaults={
                    'message': f"{instance.expediteur.prenom} {instance.expediteur.nom} vous a envoyé une demande d'amitié."
                }
            )
    else:
        # Relation modifiée - vérifier les changements de statut
        try:
            old_instance = Relation.objects.get(pk=instance.pk)
            # Cette logique sera gérée par les méthodes de modèle
        except Relation.DoesNotExist:
            pass


@receiver(post_delete, sender=Relation)
def cleanup_relation_notifications(sender, instance, **kwargs):
    """
    Nettoie les notifications liées à une relation supprimée
    """
    NotificationAmitie.objects.filter(relation=instance).delete()


# messagerie/signals.py (version améliorée)
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
import os
from .models import Message, Conversation, MessageReaction


@receiver(post_save, sender=Message)
def update_conversation_on_message_save(sender, instance, created, **kwargs):
    """
    Met à jour la conversation quand un nouveau message est créé
    """
    if created:
        # Mettre à jour les timestamps de la conversation
        conversation = instance.conversation
        conversation.last_message_at = instance.created_at
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['last_message_at', 'updated_at'])
        
        # Invalider le cache des conversations
        cache.delete_many([
            f'conversation_list_{conversation.participant1.id}',
            f'conversation_list_{conversation.participant2.id}',
            f'unread_count_{conversation.participant1.id}',
            f'unread_count_{conversation.participant2.id}',
        ])


@receiver(post_delete, sender=Message)
def update_conversation_on_message_delete(sender, instance, **kwargs):
    """
    Met à jour la conversation quand un message est supprimé
    """
    try:
        conversation = instance.conversation
        if conversation:
            # Trouver le dernier message restant
            last_message = conversation.messages.order_by('-created_at').first()
            conversation.last_message_at = last_message.created_at if last_message else conversation.created_at
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=['last_message_at', 'updated_at'])
            
            # Invalider le cache
            cache.delete_many([
                f'conversation_list_{conversation.participant1.id}',
                f'conversation_list_{conversation.participant2.id}',
            ])
    except Conversation.DoesNotExist:
        pass


@receiver(pre_delete, sender=Message)
def cleanup_message_file(sender, instance, **kwargs):
    """
    Supprime le fichier physique quand un message avec fichier est supprimé
    """
    if instance.file:
        try:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
        except (ValueError, OSError):
            pass


@receiver(post_save, sender=MessageReaction)
def invalidate_message_cache_on_reaction(sender, instance, **kwargs):
    """
    Invalide le cache des messages quand une réaction est ajoutée
    """
    cache.delete(f'message_reactions_{instance.message.id}')


@receiver(post_delete, sender=MessageReaction)
def invalidate_message_cache_on_reaction_delete(sender, instance, **kwargs):
    """
    Invalide le cache des messages quand une réaction est supprimée
    """
    cache.delete(f'message_reactions_{instance.message.id}')