from rest_framework import viewsets
from .models import Universite, Filiere
from .serializers import UniversiteSerializer, FiliereSerializer
from rest_framework.decorators import action
from rest_framework.response import Response

class FiliereViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Filiere.objects.all()
    serializer_class = FiliereSerializer


class UniversiteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Universite.objects.all()
    serializer_class = UniversiteSerializer

    @action(detail=True, methods=['get'])
    def filieres(self, request, pk=None):
        universite = self.get_object()
        filieres = universite.filieres.all()
        serializer = FiliereSerializer(filieres, many=True)
        return Response(serializer.data)
