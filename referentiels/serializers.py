from rest_framework import serializers
from .models import Universite, Filiere

class FiliereSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filiere
        fields = ['id', 'nom', 'domaine', 'Universite']


class UniversiteSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    class Meta:
        model = Universite
        fields = ['id', 'nom', 'ville', 'type', 'type_display']
