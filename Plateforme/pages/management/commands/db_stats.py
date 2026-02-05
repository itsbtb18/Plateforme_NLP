"""Show database statistics."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Show database statistics for all models'

    def handle(self, *args, **kwargs):
        from institutions.models import Institution, Country, Specialty
        from resources.models import Document, Course, Corpus, NLPTool
        from projects.models import Project
        from events.models import Event
        from forum.models import Topic
        from QA.models import Post

        self.stdout.write('=== DATABASE SUMMARY ===')
        self.stdout.write(f'Countries: {Country.objects.count()}')
        self.stdout.write(f'Specialties: {Specialty.objects.count()}')
        self.stdout.write(f'Institutions: {Institution.objects.count()}')
        self.stdout.write(f'Documents: {Document.objects.count()}')
        self.stdout.write(f'Courses: {Course.objects.count()}')
        self.stdout.write(f'Corpora: {Corpus.objects.count()}')
        self.stdout.write(f'NLP Tools: {NLPTool.objects.count()}')
        self.stdout.write(f'Projects: {Project.objects.count()}')
        self.stdout.write(f'Events: {Event.objects.count()}')
        self.stdout.write(f'Forum Topics: {Topic.objects.count()}')
        self.stdout.write(f'Posts: {Post.objects.count()}')
