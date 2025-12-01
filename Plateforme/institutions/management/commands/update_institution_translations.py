from django.core.management.base import BaseCommand
from institutions.models import Institution


class Command(BaseCommand):
    help = 'Update institution names with Arabic and English translations'

    def handle(self, *args, **kwargs):
        # Mapping of institution acronyms to their full names
        institution_translations = {
            'CDTA': {
                'name_en': 'Centre de Développement des Technologies Avancées',
                'name_ar': 'مركز تطوير التقنيات المتقدمة'
            },
            'CRNA': {
                'name_en': "Centre de Recherche Nucléaire d'Alger",
                'name_ar': 'مركز البحث النووي بالجزائر'
            },
            'CRASC': {
                'name_en': 'Centre de Recherche en Anthropologie Sociale et Culturelle',
                'name_ar': 'مركز البحث في الأنثروبولوجيا الاجتماعية والثقافية'
            },
            'CRTI': {
                'name_en': 'Centre de Recherche en Technologies Industrielles',
                'name_ar': 'مركز البحث في التكنولوجيات الصناعية'
            },
            'CRTSE': {
                'name_en': 'Centre de Recherche en Technologies Scientifiques et Educatives',
                'name_ar': 'مركز البحث في التقنيات العلمية والتربوية'
            },
            'CERIST': {
                'name_en': "Centre de Recherche sur l'Information Scientifique et Technique",
                'name_ar': 'مركز البحث في الإعلام العلمي والتقني'
            },
            'UnivBlida1': {
                'name_en': 'Université Blida 1',
                'name_ar': 'جامعة البليدة 1'
            },
            'UnivAlger1': {
                'name_en': 'Université d\'Alger 1',
                'name_ar': 'جامعة الجزائر 1'
            },
            'UnivBMA': {
                'name_en': 'Université Badji Mokhtar Annaba',
                'name_ar': 'جامعة باجي مختار عنابة'
            },
        }

        updated_count = 0
        for acronym, translations in institution_translations.items():
            try:
                institution = Institution.objects.get(acronym=acronym)
                institution.name_en = translations['name_en']
                institution.name_ar = translations['name_ar']
                institution.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated {acronym}: {translations["name_en"]} / {translations["name_ar"]}'
                    )
                )
            except Institution.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'Institution with acronym {acronym} not found')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully updated {updated_count} institutions')
        )
