# relations/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

class RelationManager(models.Manager):
    def get_amis(self, etudiant):
        relations = self.filter(
            Q(expediteur=etudiant) | Q(destinataire=etudiant),
            statut='acceptee'
        ).select_related('expediteur__utilisateur', 'destinataire__utilisateur')
        
        amis = []
        for relation in relations:
            if relation.expediteur == etudiant:
                amis.append(relation.destinataire)
            else:
                amis.append(relation.expediteur)
        return amis
    
    def get_demandes_recues(self, etudiant):
        return self.filter(
            destinataire=etudiant, 
            statut='envoyee'
        ).select_related('expediteur__utilisateur')
    
    def get_demandes_envoyees(self, etudiant):
        return self.filter(
            expediteur=etudiant
        ).select_related('destinataire__utilisateur')
    
    def get_suggestions(self, etudiant, universite_filter=None, filiere_filter=None, limit=20):
        # Import ici pour éviter les problèmes circulaires
        from accounts.models import Etudiant
        
        relations_ids = list(
            self.filter(Q(expediteur=etudiant) | Q(destinataire=etudiant))
            .values_list('expediteur__id', 'destinataire__id')
        )
        
        exclus_ids = set()
        for expediteur_id, destinataire_id in relations_ids:
            exclus_ids.add(expediteur_id)
            exclus_ids.add(destinataire_id)
        exclus_ids.add(etudiant.id)
        
        suggestions = Etudiant.objects.exclude(
            id__in=exclus_ids
        ).select_related('utilisateur', 'filiere', 'universite')
        
        if universite_filter:
            suggestions = suggestions.filter(universite_id=universite_filter)
        
        if filiere_filter:
            suggestions = suggestions.filter(filiere_id=filiere_filter)
        
        return suggestions[:limit]

class Relation(models.Model):
    STATUT_CHOICES = [
        ('envoyee', 'Demande envoyée'),
        ('acceptee', 'Demande acceptée'),
        ('refusee', 'Demande refusée'),
        ('bloquee', 'Relation bloquée'),
    ]

    # Utilisez des strings pour éviter les imports circulaires
    expediteur = models.ForeignKey(
        'accounts.Etudiant',
        on_delete=models.CASCADE,
        related_name='relations_envoyees',
        help_text="L'étudiant qui a envoyé la demande"
    )
    destinataire = models.ForeignKey(
        'accounts.Etudiant',
        on_delete=models.CASCADE,
        related_name='relations_recues',
        help_text="L'étudiant qui a reçu la demande"
    )
    statut = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        default='envoyee',
        help_text="Statut actuel de la relation"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    bloque_par = models.ForeignKey(
        'accounts.Etudiant',
        on_delete=models.CASCADE,
        related_name='relations_bloquees',
        null=True,
        blank=True,
        help_text="L'étudiant qui a bloqué la relation"
    )

    objects = RelationManager()

    class Meta:
        unique_together = ('expediteur', 'destinataire')
        ordering = ['-date_modification']
        verbose_name = "Relation d'amitié"
        verbose_name_plural = "Relations d'amitié"

    def __str__(self):
        return f"{self.expediteur} ➡ {self.destinataire} [{self.get_statut_display()}]"

    def est_ami(self):
        return self.statut == 'acceptee'
    
    def est_bloque(self):
        return self.statut == 'bloquee'
    
    def peut_envoyer_message(self):
        return self.est_ami() and not self.est_bloque()
        
    def clean(self):
        if self.expediteur == self.destinataire:
            raise ValidationError("Un étudiant ne peut pas être ami avec lui-même.")
        
        if self.pk is None:
            relation_inverse = Relation.objects.filter(
                expediteur=self.destinataire,
                destinataire=self.expediteur
            ).first()
            
            if relation_inverse and relation_inverse.statut in ['acceptee', 'envoyee']:
                raise ValidationError(
                    "Une relation existe déjà entre ces deux étudiants."
                )
        
    def save(self, *args, **kwargs):
        self.clean()
        
        if self.pk:
            try:
                ancienne_relation = Relation.objects.get(pk=self.pk)
                if ancienne_relation.statut != self.statut:
                    self.date_modification = timezone.now()
            except Relation.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def accepter(self):
        if self.statut == 'envoyee':
            self.statut = 'acceptee'
            self.save()
            return True
        return False
    
    def refuser(self):
        if self.statut == 'envoyee':
            self.statut = 'refusee'
            self.save()
            return True
        return False
    
    def bloquer(self, bloque_par):
        self.statut = 'bloquee'
        self.bloque_par = bloque_par
        self.save()
        return True
    
    def debloquer(self):
        if self.statut == 'bloquee':
            self.statut = 'refusee'
            self.bloque_par = None
            self.save()
            return True
        return False
        
    @classmethod
    def sont_amis(cls, etudiant1, etudiant2):
        return cls.objects.filter(
            Q(expediteur=etudiant1, destinataire=etudiant2) | 
            Q(expediteur=etudiant2, destinataire=etudiant1),
            statut='acceptee'
        ).exists()
    
    @classmethod
    def get_relation(cls, etudiant1, etudiant2):
        return cls.objects.filter(
            Q(expediteur=etudiant1, destinataire=etudiant2) | 
            Q(expediteur=etudiant2, destinataire=etudiant1)
        ).first()
    
    @classmethod
    def peuvent_communiquer(cls, etudiant1, etudiant2):
        relation = cls.get_relation(etudiant1, etudiant2)
        return relation and relation.peut_envoyer_message()

class NotificationAmitie(models.Model):
    TYPE_CHOICES = [
        ('demande_recue', 'Demande d\'amitié reçue'),
        ('demande_acceptee', 'Demande d\'amitié acceptée'),
        ('demande_refusee', 'Demande d\'amitié refusée'),
    ]
    
    destinataire = models.ForeignKey(
        'accounts.Etudiant',
        on_delete=models.CASCADE,
        related_name='notifications_amitie'
    )
    expediteur = models.ForeignKey(
        'accounts.Etudiant',
        on_delete=models.CASCADE,
        related_name='notifications_envoyees'
    )
    relation = models.ForeignKey(
        Relation,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type_notification = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField(blank=True)
    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"Notification pour {self.destinataire} - {self.get_type_notification_display()}"
    
    def marquer_comme_lu(self):
        if not self.lu:
            self.lu = True
            self.save(update_fields=['lu'])