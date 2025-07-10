from rest_framework import serializers
from .models import (
    CustomUser, Etudiant
)
from django.contrib.auth import authenticate
from referentiels.models import (
    Universite, Filiere
)

class EtudiantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Etudiant
        exclude = ['utilisateur']

# serializer de l'incription
class RegisterSerializer(serializers.ModelSerializer):
    ine = serializers.CharField()
    nom = serializers.CharField()
    prenom = serializers.CharField()
    telephone = serializers.CharField()
    date_naissance = serializers.DateField(required=False)
    genre = serializers.ChoiceField(choices=[('H', 'Homme'), ('F', 'Femme')])
    situation = serializers.CharField(required=False, allow_blank=True)
    ville = serializers.CharField()
    profil_prive = serializers.BooleanField(default=False)
    attestation_inscription = serializers.FileField(required=False, allow_null=True)
    photo = serializers.ImageField(required=False, allow_null=True)
    universite = serializers.PrimaryKeyRelatedField(queryset=Universite.objects.all(), required=False, allow_null=True)
    filiere = serializers.PrimaryKeyRelatedField(queryset=Filiere.objects.all(), required=False, allow_null=True)
    annee_universitaire = serializers.CharField()

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'role',
                    'ine', 'nom', 'prenom', 'telephone', 'date_naissance', 'genre',
                    'situation', 'ville', 'profil_prive', 'attestation_inscription',
                    'photo', 'universite', 'filiere', 'annee_universitaire'
                ]
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        etudiant_data = {key: validated_data.pop(key, None) for key in [
            'ine', 'nom', 'prenom', 'telephone', 'date_naissance', 'genre',
            'situation', 'ville', 'profil_prive', 'attestation_inscription',
            'photo', 'universite', 'filiere', 'annee_universitaire']}

        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role='etudiant'
        )
        Etudiant.objects.create(utilisateur=user, **etudiant_data)
        return user

# serilizer du login
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if user is None:
            raise serializers.ValidationError("Email ou mot de passe invalide")
        if not user.is_active:
            raise serializers.ValidationError("Compte inactif")
        return {'user': user}