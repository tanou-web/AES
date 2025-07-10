from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from .models import Conversation, Message, MessageReaction


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_participants', 'get_messages_count', 'get_unread_count', 'is_active', 'last_message_at', 'get_archived_status')
    list_filter = ('is_active', 'created_at', 'last_message_at', 'archived_by_participant1', 'archived_by_participant2')
    search_fields = (
        'participant1__utilisateur__username', 
        'participant2__utilisateur__username',
        'participant1__utilisateur__first_name',
        'participant1__utilisateur__last_name',
        'participant2__utilisateur__first_name',
        'participant2__utilisateur__last_name'
    )
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_message_at')
    date_hierarchy = 'created_at'
    
    def get_participants(self, obj):
        p1_name = obj.participant1.utilisateur.get_full_name() or obj.participant1.utilisateur.username
        p2_name = obj.participant2.utilisateur.get_full_name() or obj.participant2.utilisateur.username
        
        p1_url = reverse('admin:accounts_etudiant_change', args=[obj.participant1.id])
        p2_url = reverse('admin:accounts_etudiant_change', args=[obj.participant2.id])
        
        return format_html(
            '<a href="{}">{}</a> ↔ <a href="{}">{}</a>',
            p1_url, p1_name, p2_url, p2_name
        )
    get_participants.short_description = "Participants"
    
    def get_messages_count(self, obj):
        count = obj.messages.count()
        if count > 0:
            url = reverse('admin:messagerie_message_changelist') + f'?conversation__id__exact={obj.id}'
            return format_html('<a href="{}">{} messages</a>', url, count)
        return "0 messages"
    get_messages_count.short_description = "Messages"
    
    def get_unread_count(self, obj):
        unread_p1 = obj.messages.filter(receiver=obj.participant1, is_read=False).count()
        unread_p2 = obj.messages.filter(receiver=obj.participant2, is_read=False).count()
        total = unread_p1 + unread_p2
        if total > 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', total)
        return "0"
    get_unread_count.short_description = "Non lus"
    
    def get_archived_status(self, obj):
        status = []
        if obj.archived_by_participant1:
            status.append(f"Archivé par {obj.participant1.utilisateur.username}")
        if obj.archived_by_participant2:
            status.append(f"Archivé par {obj.participant2.utilisateur.username}")
        return " | ".join(status) if status else "Non archivé"
    get_archived_status.short_description = "Statut d'archivage"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'participant1__utilisateur',
            'participant2__utilisateur'
        ).annotate(
            messages_count=Count('messages')
        )
    
    actions = ['activer_conversations', 'desactiver_conversations', 'desarchiever_conversations']
    
    def activer_conversations(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} conversation(s) activée(s).")
    activer_conversations.short_description = "Activer les conversations"
    
    def desactiver_conversations(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} conversation(s) désactivée(s).")
    desactiver_conversations.short_description = "Désactiver les conversations"
    
    def desarchiever_conversations(self, request, queryset):
        count = queryset.update(archived_by_participant1=False, archived_by_participant2=False)
        self.message_user(request, f"{count} conversation(s) désarchivée(s).")
    desarchiever_conversations.short_description = "Désarchiver toutes les conversations"


class MessageReactionInline(admin.TabularInline):
    model = MessageReaction
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('user', 'reaction_type', 'created_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_conversation_link', 'get_sender_link', 'get_receiver_link', 'get_content_preview', 'message_type', 'is_read', 'is_edited', 'created_at')
    list_filter = ('message_type', 'is_read', 'is_edited', 'created_at', 'is_deleted_by_sender', 'is_deleted_by_receiver')
    search_fields = ('content', 'sender__utilisateur__username', 'receiver__utilisateur__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'read_at', 'edited_at', 'file_size', 'file_type')
    date_hierarchy = 'created_at'
    inlines = [MessageReactionInline]
    
    fieldsets = (
        ('Information générale', {
            'fields': ('id', 'conversation', 'sender', 'receiver', 'message_type')
        }),
        ('Contenu', {
            'fields': ('content', 'file', 'file_size', 'file_type', 'reply_to')
        }),
        ('États', {
            'fields': ('is_read', 'read_at', 'is_edited', 'edited_at', 'is_deleted_by_sender', 'is_deleted_by_receiver')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_conversation_link(self, obj):
        url = reverse('admin:messagerie_conversation_change', args=[obj.conversation.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.conversation)[:50])
    get_conversation_link.short_description = "Conversation"
    
    def get_sender_link(self, obj):
        url = reverse('admin:accounts_etudiant_change', args=[obj.sender.id])
        name = obj.sender.utilisateur.get_full_name() or obj.sender.utilisateur.username
        return format_html('<a href="{}">{}</a>', url, name)
    get_sender_link.short_description = "Expéditeur"
    get_sender_link.admin_order_field = 'sender__utilisateur__username'
    
    def get_receiver_link(self, obj):
        url = reverse('admin:accounts_etudiant_change', args=[obj.receiver.id])
        name = obj.receiver.utilisateur.get_full_name() or obj.receiver.utilisateur.username
        return format_html('<a href="{}">{}</a>', url, name)
    get_receiver_link.short_description = "Destinataire"
    get_receiver_link.admin_order_field = 'receiver__utilisateur__username'
    
    def get_content_preview(self, obj):
        if obj.content:
            preview = obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
            return mark_safe(preview.replace('\n', '<br>'))
        elif obj.file:
            file_name = obj.file.name.split('/')[-1]
            return format_html('<i class="fas fa-file"></i> {}', file_name)
        return "-"
    get_content_preview.short_description = "Contenu"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'conversation', 
            'sender__utilisateur', 
            'receiver__utilisateur', 
            'reply_to'
        )
    
    actions = ['marquer_comme_lu', 'marquer_comme_non_lu', 'supprimer_pour_tous']
    
    def marquer_comme_lu(self, request, queryset):
        count = 0
        for message in queryset.filter(is_read=False):
            message.mark_as_read()
            count += 1
        self.message_user(request, f"{count} message(s) marqué(s) comme lu(s).")
    marquer_comme_lu.short_description = "Marquer comme lus"
    
    def marquer_comme_non_lu(self, request, queryset):
        count = queryset.filter(is_read=True).update(is_read=False, read_at=None)
        self.message_user(request, f"{count} message(s) marqué(s) comme non lu(s).")
    marquer_comme_non_lu.short_description = "Marquer comme non lus"
    
    def supprimer_pour_tous(self, request, queryset):
        count = queryset.update(is_deleted_by_sender=True, is_deleted_by_receiver=True)
        self.message_user(request, f"{count} message(s) supprimé(s) pour tous.")
    supprimer_pour_tous.short_description = "Supprimer pour tous"


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_message_preview', 'get_user_link', 'reaction_type', 'get_reaction_emoji', 'created_at')
    list_filter = ('reaction_type', 'created_at')
    search_fields = ('user__utilisateur__username', 'message__content')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    
    def get_message_preview(self, obj):
        preview = obj.message.content[:50] + "..." if obj.message.content and len(obj.message.content) > 50 else obj.message.content or "[Fichier]"
        url = reverse('admin:messagerie_message_change', args=[obj.message.id])
        return format_html('<a href="{}">{}</a>', url, preview)
    get_message_preview.short_description = "Message"
    
    def get_user_link(self, obj):
        url = reverse('admin:accounts_etudiant_change', args=[obj.user.id])
        name = obj.user.utilisateur.get_full_name() or obj.user.utilisateur.username
        return format_html('<a href="{}">{}</a>', url, name)
    get_user_link.short_description = "Utilisateur"
    get_user_link.admin_order_field = 'user__utilisateur__username'
    
    def get_reaction_emoji(self, obj):
        return obj.get_reaction_type_display()
    get_reaction_emoji.short_description = "Emoji"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'message', 
            'user__utilisateur'
        )