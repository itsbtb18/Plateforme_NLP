from django.core.management.base import BaseCommand
from institutions.models import Institution

class Command(BaseCommand):
    help = 'Fix institution logo assignments based on correct mapping'

    def handle(self, *args, **options):
        self.stdout.write('Fixing institution logos...\n')
        
        # Correct mapping based on actual logo files
        # These are educated guesses - you may need to adjust based on what each capture shows
        logo_mapping = {
            'USTHB': 'institutions/logos/logo_m1brdi.png',  # USTHB logo (bleu)
            'UNIV-ALG1': 'institutions/logos/cropped-logo-univ1_1_o8x8h7.png',  # Univ Alger 1
            'CRTI': 'institutions/logos/crti_xysjmv.png',  # CRTI logo
            'CDTA': 'institutions/logos/Capture_décran_2025-11-17_160512_trcfsw.png',  # Largest file, likely CDTA
            'CERIST': 'institutions/logos/Capture_décran_2025-11-15_220516_r5l8ei.png',  # Medium capture
            'CRNA': 'institutions/logos/Capture_décran_2025-11-15_221033_nytwu.png',  # Small capture
        }
        
        updated_count = 0
        for acronym, logo_path in logo_mapping.items():
            try:
                institution = Institution.objects.get(acronym=acronym)
                old_logo = institution.logo
                institution.logo = logo_path
                institution.save()
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Updated {acronym}:\n'
                    f'  Old: {old_logo}\n'
                    f'  New: {logo_path}'
                ))
                updated_count += 1
            except Institution.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'✗ Institution "{acronym}" not found'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error updating {acronym}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully updated {updated_count} institution logos'))
