# messagerie/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Max
import uuid
import os


def get_message_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"messages/{instance.conversation.id}/files/{filename}"


class ConversationManager(models.Manager):
    def get_user_conversations(self, user_etudiant, include_archived=False):
        conversations = self.filter(
            Q(participant1=user_etudiant) | Q(participant2=user_etudiant)
        )
        
        if not include_archived:
            conversations = conversations.exclude(
                Q(participant1=user_etudiant, archived_by_participant1=True) |
                Q(participant2=user_etudiant, archived_by_participant2=True)
            )
        
        return conversations.select_related(
            'participant1__utilisateur', 
            'participant2__utilisateur'
        )
    
    def get_or_create_between_users(self, etudiant1, etudiant2):
        # Import ici pour éviter les problèmes circulaires
        from relations.models import Relation
        
        if not Relation.peuvent_communiquer(etudiant1, etudiant2):
            raise ValidationError("Les étudiants doivent être amis pour communiquer.")
        
        if etudiant1.id > etudiant2.id:
            etudiant1, etudiant2 = etudiant2, etudiant1
            
        conversation, created = self.get_or_create(
            participant1=etudiant1,
            participant2=etudiant2
        )
        return conversation, created


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Utilisez des strings pour éviter les imports circulaires
    participant1 = models.ForeignKey(
        'accounts.Etudiant',
        related_name='conversations_as_participant1', 
        on_delete=models.CASCADE
    )
    participant2 = models.ForeignKey(
        'accounts.Etudiant',
        related_name='conversations_as_participant2', 
        on_delete=models.CASCADE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    archived_by_participant1 = models.BooleanField(default=False)
    archived_by_participant2 = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    
    objects = ConversationManager()
    
    class Meta:
        unique_together = ('participant1', 'participant2')
        ordering = ['-last_message_at', '-updated_at']
        
    def clean(self):
        if self.participant1 == self.participant2:
            raise ValidationError("Un étudiant ne peut pas avoir une conversation avec lui-même.")
    
    def save(self, *args, **kwargs):
        if self.participant1.id > self.participant2.id:
            self.participant1, self.participant2 = self.participant2, self.participant1
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Conversation entre {self.participant1} et {self.participant2}"
    
    def get_other_participant(self, current_user_etudiant):
        if self.participant1 == current_user_etudiant:
            return self.participant2
        return self.participant1
    
    def get_last_message(self):
        return self.messages.filter(
            Q(is_deleted_by_sender=False) | Q(is_deleted_by_receiver=False)
        ).order_by('-created_at').first()
    
    def get_unread_count(self, user_etudiant):
        return self.messages.filter(
            receiver=user_etudiant, 
            is_read=False,
            is_deleted_by_receiver=False
        ).count()
    
    def is_archived_by(self, user_etudiant):
        if user_etudiant == self.participant1:
            return self.archived_by_participant1
        elif user_etudiant == self.participant2:
            return self.archived_by_participant2
        return False
    
    def archive_for_user(self, user_etudiant):
        if user_etudiant == self.participant1:
            self.archived_by_participant1 = True
        elif user_etudiant == self.participant2:
            self.archived_by_participant2 = True
        self.save(update_fields=['archived_by_participant1', 'archived_by_participant2'])
    
    def unarchive_for_user(self, user_etudiant):
        """Désarchive une conversation pour un utilisateur"""
        if user_etudiant == self.participant1:
            self.archived_by_participant1 = False
        elif user_etudiant == self.participant2:
            self.archived_by_participant2 = False
        self.save(update_fields=['archived_by_participant1', 'archived_by_participant2'])
    
    def mark_all_as_read(self, user_etudiant):
        """Marque tous les messages comme lus pour un utilisateur - version optimisée"""
        self.messages.filter(
            receiver=user_etudiant,
            is_read=False,
            is_deleted_by_receiver=False
        ).update(is_read=True, read_at=timezone.now())
    
    def can_send_message(self, user_etudiant):
        if user_etudiant not in [self.participant1, self.participant2]:
            return False
        
        # Import ici pour éviter les problèmes circulaires
        from relations.models import Relation
        other_participant = self.get_other_participant(user_etudiant)
        return Relation.peuvent_communiquer(user_etudiant, other_participant)


class MessageManager(models.Manager):
    def visible_for_user(self, user_etudiant):
        return self.filter(
            Q(sender=user_etudiant, is_deleted_by_sender=False) |
            Q(receiver=user_etudiant, is_deleted_by_receiver=False)
        )
    
    def unread_for_user(self, user_etudiant):
        return self.filter(
            receiver=user_etudiant,
            is_read=False,
            is_deleted_by_receiver=False
        )
    
    def get_conversation_messages(self, conversation, user_etudiant):
        return self.filter(
            conversation=conversation
        ).filter(
            Q(sender=user_etudiant, is_deleted_by_sender=False) |
            Q(receiver=user_etudiant, is_deleted_by_receiver=False)
        ).select_related(
            'sender__utilisateur',
            'receiver__utilisateur',
            'reply_to__sender__utilisateur'
        ).prefetch_related(
            'reactions__user__utilisateur'
        )


class Message(models.Model):
    TYPE_CHOICES = [
        ('text', 'Texte'),
        ('image', 'Image'),
        ('video', 'Vidéo'),
        ('audio', 'Audio'),
        ('file', 'Fichier'),
        ('location', 'Localisation'),
        ('sticker', 'Autocollant'),
        ('emoji', 'Emoji'),
        ('system', 'Message système'),
    ]

    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, 
        related_name='messages', 
        on_delete=models.CASCADE
    )
    
    # Utilisez des strings pour éviter les imports circulaires
    sender = models.ForeignKey(
        'accounts.Etudiant',
        related_name='sent_messages', 
        on_delete=models.CASCADE
    )
    receiver = models.ForeignKey(
        'accounts.Etudiant',
        related_name='received_messages', 
        on_delete=models.CASCADE
    )
    
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='text')
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to=get_message_file_path, blank=True, null=True)
    
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_type = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_receiver = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    
    reply_to = models.ForeignKey(
        'self', 
        blank=True, 
        null=True, 
        on_delete=models.SET_NULL,
        related_name='replies'
    )
    
    objects = MessageManager()
    
    # Dans la classe Message
    def get_file_display_name(self):
        """Retourne le nom d'affichage du fichier sans les chemins"""
        if not self.file:
           return ''
        import os
        return os.path.basename(self.file.name)
    
    class Meta:
        ordering = ['created_at']
        
    def clean(self):
        if self.sender == self.receiver:
            raise ValidationError("L'expéditeur et le destinataire ne peuvent pas être identiques.")
    
    def save(self, *args, **kwargs):
        self.clean()
        is_new = self._state.adding
        
        # Détecter automatiquement le type emoji
        if self.message_type == 'text' and self.content and self.is_emoji_only():
            self.message_type = 'emoji'
        
        if self.file:
            self.file_size = self.file.size
            if hasattr(self.file, 'content_type'):
                self.file_type = self.file.content_type
                
                if self.file_type.startswith('image/'):
                    self.message_type = 'image'
                elif self.file_type.startswith('video/'):
                    self.message_type = 'video'
                elif self.file_type.startswith('audio/'):
                    self.message_type = 'audio'
                else:
                    self.message_type = 'file'
        
        super().save(*args, **kwargs)
        
        if is_new:
            self.conversation.last_message_at = self.created_at
            self.conversation.updated_at = timezone.now()
            self.conversation.save(update_fields=['last_message_at', 'updated_at'])
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def is_visible_for(self, user_etudiant):
        if user_etudiant == self.sender:
            return not self.is_deleted_by_sender
        elif user_etudiant == self.receiver:
            return not self.is_deleted_by_receiver
        return False
    
    def is_emoji_only(self):
        """Vérifie si le message ne contient que des emojis"""
        if not self.content:
            return False
    
        import re
        # Pattern pour détecter les emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
    
        clean_content = re.sub(emoji_pattern, '', self.content).strip()
        return len(clean_content) == 0
    
    def delete_for_user(self, user_etudiant):
        if user_etudiant == self.sender:
            self.is_deleted_by_sender = True
        elif user_etudiant == self.receiver:
            self.is_deleted_by_receiver = True
        
        self.save(update_fields=['is_deleted_by_sender', 'is_deleted_by_receiver'])
        
        if self.is_deleted_by_sender and self.is_deleted_by_receiver:
            if self.file:
                try:
                    os.remove(self.file.path)
                except OSError:
                    pass
            self.delete()
    
    def get_file_size_display(self):
        if not self.file_size:
            return ''
        
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def can_be_edited(self, user_etudiant):
        """Vérifie si un message peut être édité par l'utilisateur"""
        # Un message peut être édité dans les 15 minutes après l'envoi
        # et seulement par l'expéditeur
        if self.sender != user_etudiant:
            return False
        
        time_limit = timezone.now() - timezone.timedelta(minutes=15)
        return self.created_at > time_limit and self.message_type == 'text'
    
    def edit_content(self, new_content):
        """Édite le contenu d'un message"""
        if not new_content.strip():
            return False
        
        self.content = new_content.strip()
        self.is_edited = True
        self.edited_at = timezone.now()
        self.save(update_fields=['content', 'is_edited', 'edited_at'])
        return True
    
    def __str__(self):
        content_preview = self.content[:50] + "..." if self.content and len(self.content) > 50 else self.content or f"[{self.get_message_type_display()}]"
        return f"{self.sender} → {self.receiver}: {content_preview}"
    

class MessageReaction(models.Model):
    REACTION_CHOICES = [
        ('like', '👍'),
        ('love', '❤️'),
        ('laugh', '😂'),
        ('wow', '😮'),
        ('sad', '😢'),
        ('angry', '😠'),
        ('fire', '🔥'),
        ('clap', '👏'),
    ]
    
    message = models.ForeignKey(
        Message, 
        related_name='reactions', 
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        'accounts.Etudiant',
        related_name='message_reactions', 
        on_delete=models.CASCADE
    )
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'user')
    
    def __str__(self):
        return f"{self.user} {self.get_reaction_type_display()} sur message de {self.message.sender}"


class ConversationSettings(models.Model):
    """Paramètres personnalisés pour chaque utilisateur dans une conversation"""
    
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE,
        related_name='user_settings'
    )
    user = models.ForeignKey(
        'accounts.Etudiant',
        on_delete=models.CASCADE,
        related_name='conversation_settings'
    )
    
    # Paramètres de notification
    notifications_enabled = models.BooleanField(default=True)
    sound_enabled = models.BooleanField(default=True)
    
    # Paramètres d'affichage
    theme = models.CharField(
        max_length=20,
        choices=[
            ('default', 'Par défaut'),
            ('dark', 'Sombre'),
            ('light', 'Clair')
        ],
        default='default'
    )
    
    # Paramètres de téléchargement
    auto_download_media = models.BooleanField(default=True)
    
    # Dernier message vu (pour les notifications)
    last_seen_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seen_by_settings'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('conversation', 'user')
        verbose_name = "Paramètres de conversation"
        verbose_name_plural = "Paramètres de conversations"
    
    def __str__(self):
        return f"Paramètres de {self.user} pour {self.conversation}"