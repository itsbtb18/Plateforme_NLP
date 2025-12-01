from django.core.management.base import BaseCommand
from resources.models import Corpus, NLPTool, Document, Course


class Command(BaseCommand):
    help = 'Update resource titles with Arabic and English translations'

    def handle(self, *args, **kwargs):
        # Mapping of resource titles to their translations
        resource_translations = {
            'الشبكات العصبية التلافيفية': {
                'title_en': 'CNN',
                'title_ar': 'الشبكات العصبية التلافيفية'
            },
            'نظرية الأنواع': {
                'title_en': 'Type theory',
                'title_ar': 'نظرية الأنواع'
            },
        }

        # Also check for any resources that have title_ar but not title_en
        self.stdout.write(self.style.WARNING('\nChecking for resources missing English titles...'))
        
        updated_count = 0
        
        # Check all resource types
        for model_class in [Corpus, NLPTool, Document, Course]:
            # Update known translations
            for current_title, translations in resource_translations.items():
                try:
                    resources = model_class.objects.filter(title=current_title)
                    for resource in resources:
                        resource.title_en = translations['title_en']
                        resource.title_ar = translations['title_ar']
                        resource.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Updated {model_class.__name__}: {translations["title_en"]} / {translations["title_ar"]}'
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Could not update in {model_class.__name__}: {str(e)}'
                        )
                    )
            
            # Check for resources with empty title_en and populate from title
            missing_en = model_class.objects.filter(title_en='')
            for resource in missing_en:
                # If title is in Arabic, copy it to title_ar and leave title_en empty (to be filled manually)
                if resource.title and not resource.title_ar:
                    resource.title_ar = resource.title
                    resource.save()
                    self.stdout.write(
                        self.style.WARNING(
                            f'{model_class.__name__} "{resource.title}" needs English translation'
                        )
                    )

        if updated_count == 0:
            self.stdout.write(
                self.style.WARNING('No resources found to update')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully updated {updated_count} resources')
            )
