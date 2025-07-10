from django.db import models

class Universite(models.Model):
    nom = models.CharField(max_length=255)
    ville = models.CharField(max_length=255)
    TYPE_CHOICES = [
        ('public', 'Public'),
        ('prive', 'Privé')
    ]
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    def __str__(self):
        return f"{self.nom} ({self.get_type_display()})"

    class Meta:
        ordering = ['nom']


class Filiere(models.Model):
    nom = models.CharField(max_length=20)
    domaine = models.CharField(max_length=20)
    universite = models.ForeignKey(
        Universite,
        on_delete=models.CASCADE,
        related_name='filieres'
    )

    def __str__(self):
        return f"{self.nom} - {self.universite.nom}"

    class Meta:
        ordering = ['nom']