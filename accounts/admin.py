from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, Etudiant

class CustomUserAdmin(BaseUserAdmin):
    model = CustomUser
    list_display = ('email', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    ordering = ('email',)
    search_fields = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'role', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )

admin.site.register(CustomUser, CustomUserAdmin)


class EtudiantAdmin(admin.ModelAdmin):
    list_display = ('prenom', 'nom', 'ine', 'ville', 'universite', 'filiere')
    search_fields = ('nom', 'prenom', 'ine', 'utilisateur__email')
    list_filter = ('genre', 'profil_prive', 'universite', 'filiere')
    raw_id_fields = ('utilisateur',)

admin.site.register(Etudiant, EtudiantAdmin)
