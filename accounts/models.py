# accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'email est requis")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('etudiant', 'Étudiant'),
        ('enseignant', 'Enseignant'),
        ('entreprise', 'Entreprise'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def get_full_name(self):
        """Retourne le nom complet de l'utilisateur"""
        try:
            if hasattr(self, 'etudiant') and self.etudiant:
                return self.etudiant.get_full_name()
            else:
                # Fallback sur l'email si pas d'étudiant associé
                return self.email.split('@')[0]
        except:
            return self.email.split('@')[0]
    
    def get_short_name(self):
        """Retourne le nom court"""
        try:
            if hasattr(self, 'etudiant') and self.etudiant:
                return self.etudiant.prenom
            else:
                return self.email.split('@')[0]
        except:
            return self.email.split('@')[0]
    
    @property
    def username(self):
        """Propriété pour compatibilité"""
        return self.email

    def __str__(self):
        return f"{self.email} ({self.role})"
class Etudiant(models.Model):
    utilisateur = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    ine = models.CharField(max_length=100, unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20)
    date_naissance = models.DateField(null=True, blank=True)
    genre = models.CharField(max_length=1, choices=[('H', 'Homme'), ('F', 'Femme')])
    situation = models.CharField(max_length=30, null=True, blank=True)
    ville = models.CharField(max_length=100)
    profil_prive = models.BooleanField(default=False)
    attestation_inscription = models.FileField(upload_to='attestations/', null=True, blank=True)
    photo = models.ImageField(upload_to='photos/', null=True, blank=True)
    
    # Utilisez des strings pour éviter les imports circulaires
    universite = models.ForeignKey('referentiels.Universite', on_delete=models.SET_NULL, null=True, blank=True)
    filiere = models.ForeignKey('referentiels.Filiere', on_delete=models.SET_NULL, null=True, blank=True)
    
    annee_universitaire = models.CharField(max_length=20)
    profil_prive = models.BooleanField(
        default=False, 
        help_text='Si activé, seuls les amis peuvent voir le profil complet'
    )
    
    def get_full_name(self):
         return f"{self.prenom} {self.nom}"

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.utilisateur.email})"