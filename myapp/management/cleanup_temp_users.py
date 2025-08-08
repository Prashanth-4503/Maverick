# management/commands/cleanup_temp_users.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from myapp.models import TempUserRegistration, TempOTP
from datetime import timedelta

class Command(BaseCommand):
    help = 'Cleans up expired temporary user registrations'
    
    def handle(self, *args, **options):
        # Delete temp users older than 24 hours
        cutoff = timezone.now() - timedelta(hours=24)
        count, _ = TempUserRegistration.objects.filter(
            created_at__lt=cutoff
        ).delete()
        
        self.stdout.write(f"Deleted {count} expired temporary registrations")