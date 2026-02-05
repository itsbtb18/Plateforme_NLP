from django.core.management.base import BaseCommand
from institutions.models import Institution
import os

class Command(BaseCommand):
    help = 'Assign existing logo files to institutions'

    def handle(self, *args, **options):
        self.stdout.write('Assigning logos to institutions...\n')
        
        # Mapping of institution acronyms/codes to logo filenames
        logo_mapping = {
            'CRTI': 'institutions/logos/crti_xysjmv.png',
            'UNIV-ALG1': 'institutions/logos/cropped-logo-univ1_1_o8x8h7.png',
            'USTHB': 'institutions/logos/logo_m1brdi.png',
            'CDTA': 'institutions/logos/Capture_décran_2025-11-17_160512_trcfsw.png',
            'CRNA': 'institutions/logos/Capture_décran_2025-11-15_221033_nytwu.png',
            'CERIST': 'institutions/logos/Capture_décran_2025-11-15_220516_r5l8ei.png',
        }
        
        updated_count = 0
        for acronym, logo_path in logo_mapping.items():
            try:
                institution = Institution.objects.get(acronym=acronym)
                institution.logo = logo_path
                institution.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Assigned logo to {acronym}: {logo_path}'))
                updated_count += 1
            except Institution.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'✗ Institution with acronym "{acronym}" not found'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error assigning logo to {acronym}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully assigned {updated_count} logos'))
