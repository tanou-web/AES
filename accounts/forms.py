from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from .models import CustomUser, Etudiant
from referentiels.models import Universite, Filiere
import re

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Créez un mot de passe sécurisé',
            'id': 'password-field'
        }),
        min_length=8,
        help_text="Au moins 8 caractères avec lettres et chiffres"
    )
    confirm_password = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Confirmez votre mot de passe',
            'id': 'confirm-password-field'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'votre.email@example.com',
                'id': 'email-field'
            })
        }
        labels = {
            'email': 'Adresse email'
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError("Cette adresse email est déjà utilisée.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            raise ValidationError("Le mot de passe doit contenir au moins une lettre et un chiffre.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise ValidationError("Les mots de passe ne correspondent pas.")
        
        return cleaned_data

class EtudiantRegistrationForm(forms.ModelForm):
    universite = forms.ModelChoiceField(
        queryset=Universite.objects.all().order_by('nom'),
        empty_label="🏫 Sélectionnez votre université",
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg',
            'id': 'id_universite'
        }),
        label="Université"
    )
    
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.none(),
        empty_label="📚 Sélectionnez d'abord une université",
        widget=forms.Select(attrs={
            'class': 'form-select form-select-lg',
            'id': 'id_filiere'
        }),
        label="Filière d'études"
    )
    
    class Meta:
        model = Etudiant
        fields = [
            'ine', 'nom', 'prenom', 'telephone', 
            'date_naissance', 'genre', 'ville',
            'universite', 'filiere', 'annee_universitaire',
            'attestation_inscription', 'photo'
        ]
        widgets = {
            'ine': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '🆔 Votre numéro INE'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '👤 Votre nom de famille'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '👤 Votre prénom'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '📞 +226 XX XX XX XX'
            }),
            'date_naissance': forms.DateInput(attrs={
                'class': 'form-control form-control-lg',
                'type': 'date'
            }),
            'genre': forms.Select(attrs={
                'class': 'form-select form-select-lg'
            }),
            'ville': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '🏙️ Votre ville de résidence'
            }),
            'annee_universitaire': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '📅 Ex: 2024-2025'
            }),
            'attestation_inscription': forms.FileInput(attrs={
                'class': 'form-control form-control-lg',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-control form-control-lg',
                'accept': 'image/*'
            }),
        }
        labels = {
            'ine': 'Numéro INE',
            'nom': 'Nom de famille',
            'prenom': 'Prénom',
            'telephone': 'Numéro de téléphone',
            'date_naissance': 'Date de naissance',
            'genre': 'Genre',
            'ville': 'Ville de résidence',
            'annee_universitaire': 'Année universitaire',
            'attestation_inscription': 'Attestation d\'inscription (PDF/Image)',
            'photo': 'Photo de profil (optionnel)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Mise à jour dynamique des filières
        if 'universite' in self.data:
            try:
                universite_id = int(self.data.get('universite'))
                self.fields['filiere'].queryset = Filiere.objects.filter(
                    universite_id=universite_id 
                ).order_by('nom')
                self.fields['filiere'].widget.attrs['data-loaded'] = 'true'
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.universite:
            self.fields['filiere'].queryset = Filiere.objects.filter(
                universite=self.instance.universite
            ).order_by('nom')

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        # Validation du format de téléphone burkinabè
        if not re.match(r'^\+226\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}$', telephone):
            raise ValidationError("Format invalide. Utilisez: +226 XX XX XX XX")
        return telephone

    def clean_ine(self):
        ine = self.cleaned_data.get('ine')
        if Etudiant.objects.filter(ine=ine).exists():
            raise ValidationError("Ce numéro INE est déjà utilisé.")
        return ine

class ModernLoginForm(forms.Form):
    email = forms.EmailField(
        label='Adresse email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'votre.email@example.com',
            'id': 'login-email',
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Votre mot de passe',
            'id': 'login-password',
            'autocomplete': 'current-password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'remember-me'
        }),
        label='Se souvenir de moi'
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise ValidationError("Email ou mot de passe incorrect.")
            if not user.is_active:
                raise ValidationError("Ce compte est désactivé.")
            cleaned_data['user'] = user
        
        return cleaned_data

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Etudiant
        fields = [
            'nom', 'prenom', 'telephone', 'date_naissance',
            'ville', 'situation', 'photo', 'profil_prive'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Votre nom'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Votre prénom'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+226 XX XX XX XX'
            }),
            'date_naissance': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'ville': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Votre ville'
            }),
            'situation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Décrivez votre situation actuelle...'
            }),
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'profil_prive': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'nom': 'Nom de famille',
            'prenom': 'Prénom',
            'telephone': 'Téléphone',
            'date_naissance': 'Date de naissance',
            'ville': 'Ville',
            'situation': 'Situation actuelle',
            'photo': 'Photo de profil',
            'profil_prive': 'Profil privé'
        }