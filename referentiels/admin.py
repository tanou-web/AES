from django.contrib import admin
from .models import Universite, Filiere

@admin.register(Universite)
class UniversiteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ville', 'type')
    search_fields = ('nom', 'ville')
    list_filter = ('type',)

@admin.register(Filiere)
class FiliereAdmin(admin.ModelAdmin):
    list_display = ('nom', 'domaine')
    search_fields = ('nom', 'domaine')

