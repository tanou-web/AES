
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from .models import Relation, NotificationAmitie


@admin.register(Relation)
class RelationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_expediteur_link', 'get_destinataire_link', 'statut', 'get_bloque_par', 'date_creation', 'date_modification')
    list_filter = ('statut', 'date_creation', 'date_modification', 'bloque_par')
    search_fields = (
        'expediteur__utilisateur__username', 
        'expediteur__utilisateur__first_name', 
        'expediteur__utilisateur__last_name',
        'destinataire__utilisateur__username',
        'destinataire__utilisateur__first_name',
        'destinataire__utilisateur__last_name'
    )
    readonly_fields = ('id', 'date_creation', 'date_modification')
    date_hierarchy = 'date_creation'
    
    fieldsets = (
        ('Participants', {
            'fields': ('expediteur', 'destinataire')
        }),
        ('État de la relation', {
            'fields': ('statut', 'bloque_par')
        }),
        ('Métadonnées', {
            'fields': ('id', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        })
    )
    
    def get_expediteur_link(self, obj):
        url = reverse('admin:accounts_etudiant_change', args=[obj.expediteur.id])
        return format_html('<a href="{}">{}</a>', url, obj.expediteur)
    get_expediteur_link.short_description = "Expéditeur"
    get_expediteur_link.admin_order_field = 'expediteur__utilisateur__username'
    
    def get_destinataire_link(self, obj):
        url = reverse('admin:accounts_etudiant_change', args=[obj.destinataire.id])
        return format_html('<a href="{}">{}</a>', url, obj.destinataire)
    get_destinataire_link.short_description = "Destinataire"
    get_destinataire_link.admin_order_field = 'destinataire__utilisateur__username'
    
    def get_bloque_par(self, obj):
        if obj.bloque_par:
            url = reverse('admin:accounts_etudiant_change', args=[obj.bloque_par.id])
            return format_html('<a href="{}">{}</a>', url, obj.bloque_par)
        return "-"
    get_bloque_par.short_description = "Bloqué par"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'expediteur__utilisateur',
            'destinataire__utilisateur',
            'bloque_par__utilisateur'
        )
    
    actions = ['accepter_demandes', 'refuser_demandes', 'debloquer_relations']
    
    def accepter_demandes(self, request, queryset):
        count = 0
        for relation in queryset.filter(statut='envoyee'):
            relation.accepter()
            count += 1
        self.message_user(request, f"{count} demande(s) acceptée(s).")
    accepter_demandes.short_description = "Accepter les demandes sélectionnées"
    
    def refuser_demandes(self, request, queryset):
        count = 0
        for relation in queryset.filter(statut='envoyee'):
            relation.refuser()
            count += 1
        self.message_user(request, f"{count} demande(s) refusée(s).")
    refuser_demandes.short_description = "Refuser les demandes sélectionnées"
    
    def debloquer_relations(self, request, queryset):
        count = 0
        for relation in queryset.filter(statut='bloquee'):
            relation.debloquer()
            count += 1
        self.message_user(request, f"{count} relation(s) débloquée(s).")
    debloquer_relations.short_description = "Débloquer les relations sélectionnées"


@admin.register(NotificationAmitie)
class NotificationAmitieAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_destinataire_link', 'get_expediteur_link', 'type_notification', 'lu', 'date_creation')
    list_filter = ('type_notification', 'lu', 'date_creation')
    search_fields = (
        'destinataire__utilisateur__username',
        'expediteur__utilisateur__username',
        'message'
    )
    readonly_fields = ('id', 'date_creation')
    date_hierarchy = 'date_creation'
    
    def get_destinataire_link(self, obj):
        url = reverse('admin:accounts_etudiant_change', args=[obj.destinataire.id])
        return format_html('<a href="{}">{}</a>', url, obj.destinataire)
    get_destinataire_link.short_description = "Destinataire"
    get_destinataire_link.admin_order_field = 'destinataire__utilisateur__username'
    
    def get_expediteur_link(self, obj):
        url = reverse('admin:accounts_etudiant_change', args=[obj.expediteur.id])
        return format_html('<a href="{}">{}</a>', url, obj.expediteur)
    get_expediteur_link.short_description = "Expéditeur"
    get_expediteur_link.admin_order_field = 'expediteur__utilisateur__username'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'destinataire__utilisateur',
            'expediteur__utilisateur',
            'relation'
        )
    
    actions = ['marquer_comme_lu', 'marquer_comme_non_lu']
    
    def marquer_comme_lu(self, request, queryset):
        count = queryset.update(lu=True)
        self.message_user(request, f"{count} notification(s) marquée(s) comme lue(s).")
    marquer_comme_lu.short_description = "Marquer comme lues"
    
    def marquer_comme_non_lu(self, request, queryset):
        count = queryset.update(lu=False)
        self.message_user(request, f"{count} notification(s) marquée(s) comme non lues.")
    marquer_comme_non_lu.short_description = "Marquer comme non lues"