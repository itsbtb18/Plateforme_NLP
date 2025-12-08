from django.core.management.base import BaseCommand
from institutions.models import Institution


class Command(BaseCommand):
    help = 'Update institution names with real names'

    def handle(self, *args, **kwargs):
        # Mapping des noms génériques aux vrais noms
        institution_updates = {
            'Institution 3': {
                'name': 'Centre de Recherche sur l\'Information Scientifique et Technique',
                'acronym': 'CERIST'
            },
            'Institution 4': {
                'name': 'Centre de Recherche en Technologies Scientifiques et Educatives',
                'acronym': 'CRTSE'
            },
            'Institution 5': {
                'name': 'Centre de Recherche Nucléaire d\'Alger',
                'acronym': 'CRNA'
            },
            'Institution 6': {
                'name': 'Centre de Recherche en Technologies Industrielles',
                'acronym': 'CRTI'
            },
            'Institution 7': {
                'name': 'Université de Blida 1',
                'acronym': 'UnivBlida1'
            },
            'Institution 8': {
                'name': 'Université d\'Alger 1 Benyoucef Benkhedda',
                'acronym': 'UnivAlger1'
            },
            'Institution 9': {
                'name': 'Université Badji Mokhtar Annaba',
                'acronym': 'UnivBMA'
            },
            'Institution 10': {
                'name': 'Centre de Développement des Technologies Avancées',
                'acronym': 'CDTA'
            },
            'Institution 11': {
                'name': 'Centre de Recherche en Anthropologie Sociale et Culturelle',
                'acronym': 'CRASC'
            },
        }

        updated_count = 0
        
        for old_name, new_data in institution_updates.items():
            try:
                institution = Institution.objects.get(name=old_name)
                institution.name = new_data['name']
                institution.acronym = new_data['acronym']
                institution.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated: {old_name} -> {new_data["name"]} ({new_data["acronym"]})'
                    )
                )
            except Institution.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'⚠ Institution not found: {old_name}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error updating {old_name}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully updated {updated_count} institutions')
        )
