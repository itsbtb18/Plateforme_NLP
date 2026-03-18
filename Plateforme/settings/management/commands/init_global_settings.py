"""
Management command to initialize global settings
Usage: python manage.py init_global_settings
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from settings.models import GlobalSettings


class Command(BaseCommand):
    help = 'Initialize global settings for the platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset settings to defaults',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Initializing Settings App'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Run migrations
        self.stdout.write('\n[1/2] Running migrations...')
        try:
            call_command('migrate', 'settings', verbosity=0)
            self.stdout.write(self.style.SUCCESS('✓ Migrations completed successfully'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Migration failed: {e}'))
            return

        # Create or reset settings
        self.stdout.write('\n[2/2] Setting up Global Settings...')
        try:
            if options['reset']:
                GlobalSettings.objects.all().delete()
                self.stdout.write(self.style.WARNING('   Deleted existing settings'))

            settings, created = GlobalSettings.objects.get_or_create(pk=1)
            
            if created:
                self.stdout.write(self.style.SUCCESS('✓ Global Settings created'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ Global Settings found'))

            self.stdout.write(f'   Site Name: {settings.site_name}')
            self.stdout.write(f'   Site URL: {settings.site_url}')
            self.stdout.write(f'   Admin Email: {settings.admin_email}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to create settings: {e}'))
            return

        self.stdout.write('\n' + self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('✓ Settings app initialization complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('\nYou can now manage settings in Django admin:')
        self.stdout.write('  → /admin/settings/globalsettings/')
