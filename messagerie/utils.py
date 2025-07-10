from django.db.models import Q, Count, Max
from django.core.cache import cache
from django.utils import timezone
from .models import Conversation, Message


def get_unread_messages_count(etudiant):
    """
    Récupère le nombre total de messages non lus pour un étudiant
    """
    cache_key = f'unread_count_{etudiant.id}'
    count = cache.get(cache_key)
    
    if count is None:
        count = Message.objects.filter(
            receiver=etudiant,
            is_read=False,
            is_deleted_by_receiver=False
        ).count()
        
        # Cache pour 2 minutes
        cache.set(cache_key, count, 120)
    
    return count


def get_conversations_with_metadata(etudiant, include_archived=False):
    """
    Récupère les conversations avec métadonnées optimisées
    """
    cache_key = f'conversations_metadata_{etudiant.id}_{include_archived}'
    conversations_data = cache.get(cache_key)
    
    if conversations_data is None:
        conversations = Conversation.objects.get_user_conversations(
            etudiant, 
            include_archived=include_archived
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(
                    messages__receiver=etudiant,
                    messages__is_read=False,
                    messages__is_deleted_by_receiver=False
                )
            ),
            last_message_time=Max('messages__created_at')
        ).select_related(
            'participant1__utilisateur',
            'participant2__utilisateur'
        ).prefetch_related(
            'messages'
        )
        
        conversations_data = []
        for conv in conversations:
            other_participant = conv.get_other_participant(etudiant)
            last_message = conv.get_last_message()
            
            conversations_data.append({
                'conversation': conv,
                'other_participant': {
                    'id': other_participant.id,
                    'name': other_participant.utilisateur.get_full_name() or other_participant.utilisateur.username,
                    'photo_url': other_participant.photo.url if other_participant.photo else None,
                },
                'last_message': {
                    'content': last_message.content if last_message else None,
                    'type': last_message.message_type if last_message else None,
                    'time': last_message.created_at if last_message else None,
                    'sender_is_me': last_message.sender == etudiant if last_message else False,
                } if last_message else None,
                'unread_count': conv.unread_count,
                'is_archived': conv.is_archived_by(etudiant),
                'last_activity': conv.last_message_at or conv.created_at,
            })
        
        # Trier par dernière activité
        conversations_data.sort(key=lambda x: x['last_activity'], reverse=True)
        
        # Cache pour 5 minutes
        cache.set(cache_key, conversations_data, 300)
    
    return conversations_data


def invalidate_conversation_cache(etudiant):
    """
    Invalide le cache des conversations pour un étudiant
    """
    cache.delete_many([
        f'conversations_metadata_{etudiant.id}_True',
        f'conversations_metadata_{etudiant.id}_False',
        f'unread_count_{etudiant.id}',
    ])


def format_file_size(size_bytes):
    """
    Formate la taille d'un fichier en unités lisibles
    """
    if not size_bytes:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def is_media_file(file_path):
    """
    Vérifie si un fichier est un fichier média
    """
    media_extensions = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'],
        'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'],
        'audio': ['.mp3', '.wav', '.ogg', '.aac', '.flac', '.m4a']
    }
    
    if not file_path:
        return False, None
    
    ext = file_path.lower().split('.')[-1] if '.' in file_path else ''
    ext = f'.{ext}'
    
    for media_type, extensions in media_extensions.items():
        if ext in extensions:
            return True, media_type
    
    return False, None


def get_message_search_results(etudiant, query, conversation_id=None, limit=50):
    """
    Recherche dans les messages avec mise en cache des résultats fréquents
    """
    cache_key = f'search_{etudiant.id}_{hash(query)}_{conversation_id}_{limit}'
    results = cache.get(cache_key)
    
    if results is None:
        messages_qs = Message.objects.visible_for_user(etudiant).filter(
            content__icontains=query
        )
        
        if conversation_id:
            messages_qs = messages_qs.filter(conversation_id=conversation_id)
        
        messages_qs = messages_qs.select_related(
            'conversation',
            'sender__utilisateur',
            'receiver__utilisateur'
        ).order_by('-created_at')[:limit]
        
        results = []
        for message in messages_qs:
            other_participant = message.conversation.get_other_participant(etudiant)
            results.append({
                'message_id': str(message.id),
                'conversation_id': str(message.conversation.id),
                'content': message.content,
                'sender_name': message.sender.utilisateur.get_full_name() or message.sender.utilisateur.username,
                'other_participant_name': other_participant.utilisateur.get_full_name() or other_participant.utilisateur.username,
                'created_at': message.created_at,
                'formatted_time': message.created_at.strftime('%d/%m/%Y %H:%M'),
                'is_sent': message.sender == etudiant,
            })
        
        # Cache pour 10 minutes pour les recherches courantes
        if len(query) > 2:  # Seulement pour les recherches substantielles
            cache.set(cache_key, results, 600)
    
    return results


def cleanup_old_files():
    """
    Nettoie les anciens fichiers de messages supprimés
    """
    import os
    from django.conf import settings
    from datetime import timedelta
    
    # Supprimer les fichiers de messages supprimés depuis plus de 30 jours
    cutoff_date = timezone.now() - timedelta(days=30)
    
    deleted_messages = Message.objects.filter(
        is_deleted_by_sender=True,
        is_deleted_by_receiver=True,
        updated_at__lt=cutoff_date,
        file__isnull=False
    )
    
    for message in deleted_messages:
        if message.file:
            try:
                if os.path.isfile(message.file.path):
                    os.remove(message.file.path)
            except (ValueError, OSError):
                pass
    
    # Supprimer les enregistrements de base de données
    deleted_messages.delete()


def get_conversation_analytics(conversation, etudiant):
    """
    Récupère les analyses d'une conversation
    """
    messages = Message.objects.filter(conversation=conversation)
    
    # Messages envoyés vs reçus
    sent_count = messages.filter(sender=etudiant).count()
    received_count = messages.filter(receiver=etudiant).count()
    
    # Types de messages
    message_types = messages.values('message_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Activité par jour de la semaine
    from django.db.models import Extract
    activity_by_day = messages.annotate(
        weekday=Extract('created_at', 'week_day')
    ).values('weekday').annotate(
        count=Count('id')
    ).order_by('weekday')
    
    # Période la plus active
    activity_by_hour = messages.annotate(
        hour=Extract('created_at', 'hour')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    return {
        'total_messages': messages.count(),
        'sent_count': sent_count,
        'received_count': received_count,
        'message_types': list(message_types),
        'activity_by_day': list(activity_by_day),
        'activity_by_hour': list(activity_by_hour),
        'conversation_duration': (
            timezone.now() - conversation.created_at
        ).days,
        'avg_messages_per_day': (
            messages.count() / max(1, (timezone.now() - conversation.created_at).days)
        ),
    }