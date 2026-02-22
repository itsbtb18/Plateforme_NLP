"""
Management command to check the moderation system status.

Usage:
    python manage.py check_moderation
"""
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Check the moderation system status and display pending/approved counts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed information including recent items',
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Check specific model only (e.g., "Corpus", "Event", "Project")',
        )

    def handle(self, *args, **options):
        detailed = options['detailed']
        specific_model = options.get('model')
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('MODERATION SYSTEM STATUS CHECK'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        # Models with moderation
        moderated_models = {
            'resources.Corpus': 'author',
            'resources.NLPTool': 'author',
            'resources.Course': 'author',
            'resources.Document': 'author',
            'projects.Project': 'coordinator',
            'events.Event': 'created_by',
            'forum.Topic': 'creator',
            'institutions.Institution': 'created_by',
            'QA.Post': 'author',
        }
        
        for model_path, author_field in moderated_models.items():
            app_label, model_name = model_path.split('.')
            
            # Skip if specific model requested and this isn't it
            if specific_model and model_name.lower() != specific_model.lower():
                continue
            
            try:
                Model = apps.get_model(app_label, model_name)
                
                # Check if model has approval_status field
                if not hasattr(Model, 'approval_status'):
                    self.stdout.write(
                        self.style.WARNING(
                            f'✗ {model_name}: No approval_status field (skipped)'
                        )
                    )
                    continue
                
                # Get counts
                total = Model.objects.count()
                pending = Model.objects.filter(approval_status='pending').count()
                approved = Model.objects.filter(approval_status='approved').count()
                rejected = Model.objects.filter(approval_status='rejected').count()
                
                # Display summary
                self.stdout.write(self.style.SUCCESS(f'\n{model_name.upper()}:'))
                self.stdout.write(f'  Total: {total}')
                self.stdout.write(
                    self.style.WARNING(f'  Pending: {pending}') if pending > 0 
                    else f'  Pending: {pending}'
                )
                self.stdout.write(f'  Approved: {approved}')
                self.stdout.write(f'  Rejected: {rejected}')
                
                # Detailed information
                if detailed:
                    # Recent pending items
                    recent_pending = Model.objects.filter(
                        approval_status='pending'
                    ).order_by('-created_at')[:5]
                    
                    if recent_pending.exists():
                        self.stdout.write('\n  Recent Pending Items:')
                        for item in recent_pending:
                            created_at = getattr(item, 'created_at', None)
                            title = self._get_title(item)
                            author = getattr(item, author_field, None)
                            author_email = author.email if author else 'Unknown'
                            
                            created_str = created_at.strftime('%Y-%m-%d %H:%M') if created_at else 'Unknown'
                            self.stdout.write(
                                f'    - [{created_str}] {title[:50]} by {author_email}'
                            )
                    
                    # Items created in last 24 hours
                    yesterday = timezone.now() - timedelta(days=1)
                    recent_created = Model.objects.filter(
                        created_at__gte=yesterday
                    ).count()
                    
                    if recent_created > 0:
                        self.stdout.write(f'\n  Created in last 24h: {recent_created}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Error checking {model_name}: {str(e)}'
                    )
                )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('Check complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
    
    def _get_title(self, obj):
        """Get title from object, handling different field names."""
        for field in ['title', 'name', '__str__']:
            if field == '__str__':
                return str(obj)
            if hasattr(obj, field):
                return getattr(obj, field, '')
        return 'No title'
