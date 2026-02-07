from django.core.management.base import BaseCommand
from institutions.models import Country, Specialty, Institution


class Command(BaseCommand):
    help = 'Load Algerian institutions with bilingual data'

    def handle(self, *args, **options):
        self.stdout.write('Loading Algerian institutions...')

        # Create Algeria country
        algeria, created = Country.objects.get_or_create(
            code='DZ',
            defaults={
                'name_en': 'Algeria',
                'name_ar': 'الجزائر'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created country: {algeria}'))

        # Create specialties
        specialties_data = [
            ('CS', 'Computer Science', 'علوم الحاسوب'),
            ('AI', 'Artificial Intelligence', 'الذكاء الاصطناعي'),
            ('NLP', 'Natural Language Processing', 'معالجة اللغة الطبيعية'),
            ('ML', 'Machine Learning', 'التعلم الآلي'),
            ('LING', 'Linguistics', 'اللسانيات'),
            ('MATH', 'Mathematics', 'الرياضيات'),
        ]

        specialties = []
        for code, name_en, name_ar in specialties_data:
            specialty, created = Specialty.objects.get_or_create(
                code=code,
                defaults={
                    'name_en': name_en,
                    'name_ar': name_ar
                }
            )
            specialties.append(specialty)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created specialty: {specialty}'))

        # Create Algerian research institutions
        institutions_data = [
            {
                'name_en': 'Center for Research in Scientific and Technical Information',
                'name_ar': 'مركز البحث في الإعلام العلمي والتقني',
                'acronym': 'CERIST',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.cerist.dz',
                'specialties_codes': ['CS', 'AI', 'NLP'],
            },
            {
                'name_en': 'Research Center in Industrial Technologies',
                'name_ar': 'مركز البحث في التقنيات الصناعية',
                'acronym': 'CRTI',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.crti.dz',
                'specialties_codes': ['CS', 'AI'],
            },
            {
                'name_en': 'Center for Development of Advanced Technologies',
                'name_ar': 'مركز تطوير التقنيات المتقدمة',
                'acronym': 'CDTA',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.cdta.dz',
                'specialties_codes': ['AI', 'ML', 'NLP'],
            },
            {
                'name_en': 'Nuclear Research Center of Algiers',
                'name_ar': 'مركز البحوث النووية بالجزائر',
                'acronym': 'CRNA',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.crna.dz',
                'specialties_codes': ['CS', 'MATH'],
            },
            {
                'name_en': 'University of Algiers 1',
                'name_ar': 'جامعة الجزائر 1',
                'acronym': 'UNIV-ALG1',
                'type': 'University',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.univ-alger.dz',
                'specialties_codes': ['CS', 'MATH', 'LING'],
            },
            {
                'name_en': 'University of Sciences and Technology Houari Boumediene',
                'name_ar': 'جامعة العلوم والتكنولوجيا هواري بومدين',
                'acronym': 'USTHB',
                'type': 'University',
                'city': 'Algiers',
                'city_en': 'Bab Ezzouar',
                'city_ar': 'باب الزوار',
                'website': 'https://www.usthb.dz',
                'specialties_codes': ['CS', 'AI', 'ML', 'MATH'],
            },
        ]

        for inst_data in institutions_data:
            # Get specialties
            spec_codes = inst_data.pop('specialties_codes', [])
            inst_specialties = Specialty.objects.filter(code__in=spec_codes)

            # Create institution
            institution, created = Institution.objects.get_or_create(
                acronym=inst_data['acronym'],
                defaults={
                    **inst_data,
                    'country': algeria,
                }
            )

            if created:
                institution.specialties.set(inst_specialties)
                self.stdout.write(self.style.SUCCESS(f'Created institution: {institution}'))
            else:
                self.stdout.write(self.style.WARNING(f'Institution already exists: {institution}'))

        self.stdout.write(self.style.SUCCESS('Successfully loaded Algerian institutions!'))
