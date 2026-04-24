"""
Management command to clean up old read notifications.
Deletes notifications that have been read and are older than the specified number of days.

Usage:
    python manage.py cleanup_notifications           # Default: 30 days
    python manage.py cleanup_notifications --days 60  # Custom: 60 days
    python manage.py cleanup_notifications --dry-run  # Preview without deleting
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Delete read notifications older than N days (default: 30)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete read notifications older than this many days (default: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_notifications = Notification.objects.filter(
            read=True,
            created_at__lt=cutoff_date
        )
        
        count = old_notifications.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] Would delete {count} read notifications older than {days} days.'
                )
            )
        else:
            deleted_count, _ = old_notifications.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted_count} read notifications older than {days} days.'
                )
            )
