# messagerie/management/commands/cleanup_messages.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from messagerie.models import Message


class Command(BaseCommand):
    help = 'Nettoie les anciens messages supprimés'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Nombre de jours après lesquels supprimer les messages (défaut: 30)',
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Supprimer les messages supprimés depuis plus de X jours
        deleted_messages = Message.objects.filter(
            is_deleted_by_sender=True,
            is_deleted_by_receiver=True,
            updated_at__lt=cutoff_date
        )
        
        count = deleted_messages.count()
        
        # Supprimer les fichiers associés
        for message in deleted_messages:
            if message.file:
                try:
                    message.file.delete()
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Erreur suppression fichier {message.file.name}: {e}')
                    )
        
        # Supprimer les enregistrements
        deleted_messages.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Supprimé {count} messages anciens de plus de {days} jours')
        )