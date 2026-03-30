from django.core.management.base import BaseCommand
from feed.models import Post

class Command(BaseCommand):
    help = 'Delete all news posts'

    def handle(self, *args, **options):
        count = Post.objects.count()
        Post.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✓ Deleted {count} news posts'))
        self.stdout.write(self.style.SUCCESS(f'Total posts remaining: {Post.objects.count()}'))
