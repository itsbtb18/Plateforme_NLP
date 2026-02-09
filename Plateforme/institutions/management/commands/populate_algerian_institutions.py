from django.core.management.base import BaseCommand
from institutions.models import Country, Specialty, Institution
from django.core.files import File
from pathlib import Path
import os


class Command(BaseCommand):
    help = 'Populate Algerian institutions with logos and websites'

    def handle(self, *args, **options):
        self.stdout.write('Populating Algerian institutions...\n')

        # Get or create Algeria
        algeria, _ = Country.objects.get_or_create(
            code='DZ',
            defaults={'name_en': 'Algeria', 'name_ar': 'الجزائر'}
        )

        # Get or create specialties
        cs_specialty, _ = Specialty.objects.get_or_create(
            code='CS',
            defaults={'name_en': 'Computer Science', 'name_ar': 'علوم الحاسوب'}
        )
        ai_specialty, _ = Specialty.objects.get_or_create(
            code='AI',
            defaults={'name_en': 'Artificial Intelligence', 'name_ar': 'الذكاء الاصطناعي'}
        )
        nlp_specialty, _ = Specialty.objects.get_or_create(
            code='NLP',
            defaults={'name_en': 'Natural Language Processing', 'name_ar': 'معالجة اللغة الطبيعية'}
        )

        # Institutions data with logos and websites
        institutions = [
            {
                'name': 'Centre de Recherche sur l\'Information Scientifique et Technique',
                'name_en': 'Research Center on Scientific and Technical Information',
                'name_ar': 'مركز البحث في الإعلام العلمي والتقني',
                'acronym': 'CERIST',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.cerist.dz',
                'email': 'contact@cerist.dz',
                'description': 'Centre de recherche spécialisé dans les technologies de l\'information',
                'specialties': [cs_specialty, ai_specialty, nlp_specialty],
            },
            {
                'name': 'Centre de Développement des Technologies Avancées',
                'name_en': 'Center for Development of Advanced Technologies',
                'name_ar': 'مركز تطوير التقنيات المتقدمة',
                'acronym': 'CDTA',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.cdta.dz',
                'email': 'contact@cdta.dz',
                'description': 'Centre de recherche en technologies avancées',
                'specialties': [cs_specialty, ai_specialty],
            },
            {
                'name': 'Centre de Recherche en Technologies Industrielles',
                'name_en': 'Research Center in Industrial Technologies',
                'name_ar': 'مركز البحث في التقنيات الصناعية',
                'acronym': 'CRTI',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.crti.dz',
                'email': 'contact@crti.dz',
                'description': 'Centre de recherche en technologies industrielles',
                'specialties': [cs_specialty, ai_specialty],
            },
            {
                'name': 'Centre de Recherche Nucléaire d\'Alger',
                'name_en': 'Nuclear Research Center of Algiers',
                'name_ar': 'مركز البحوث النووية بالجزائر',
                'acronym': 'CRNA',
                'type': 'Research Center',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.crna.dz',
                'email': 'contact@crna.dz',
                'description': 'Centre de recherche nucléaire',
                'specialties': [cs_specialty],
            },
            {
                'name': 'Université des Sciences et de la Technologie Houari Boumediene',
                'name_en': 'University of Science and Technology Houari Boumediene',
                'name_ar': 'جامعة العلوم والتكنولوجيا هواري بومدين',
                'acronym': 'USTHB',
                'type': 'University',
                'city': 'Algiers',
                'city_en': 'Bab Ezzouar',
                'city_ar': 'باب الزوار',
                'website': 'https://www.usthb.dz',
                'email': 'contact@usthb.dz',
                'description': 'Université spécialisée en sciences et technologies',
                'specialties': [cs_specialty, ai_specialty, nlp_specialty],
            },
            {
                'name': 'Université d\'Alger 1',
                'name_en': 'University of Algiers 1',
                'name_ar': 'جامعة الجزائر 1',
                'acronym': 'UNIV-ALG1',
                'type': 'University',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.univ-alger.dz',
                'email': 'contact@univ-alger.dz',
                'description': 'Université pluridisciplinaire',
                'specialties': [cs_specialty, nlp_specialty],
            },
            {
                'name': 'École Nationale Supérieure d\'Informatique',
                'name_en': 'National Higher School of Computer Science',
                'name_ar': 'المدرسة الوطنية العليا للإعلام الآلي',
                'acronym': 'ESI',
                'type': 'School',
                'city': 'Algiers',
                'city_en': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'website': 'https://www.esi.dz',
                'email': 'contact@esi.dz',
                'description': 'École spécialisée en informatique',
                'specialties': [cs_specialty, ai_specialty, nlp_specialty],
            },
            {
                'name': 'Université Abderrahmane Mira de Bejaia',
                'name_en': 'Abderrahmane Mira University of Bejaia',
                'name_ar': 'جامعة عبد الرحمان ميرة ببجاية',
                'acronym': 'UAMB',
                'type': 'University',
                'city': 'Bejaia',
                'city_en': 'Bejaia',
                'city_ar': 'بجاية',
                'website': 'https://www.univ-bejaia.dz',
                'email': 'contact@univ-bejaia.dz',
                'description': 'Université de Bejaia',
                'specialties': [cs_specialty],
            },
            {
                'name': 'Université Badji Mokhtar Annaba',
                'name_en': 'Badji Mokhtar Annaba University',
                'name_ar': 'جامعة باجي مختار عنابة',
                'acronym': 'UBMA',
                'type': 'University',
                'city': 'Annaba',
                'city_en': 'Annaba',
                'city_ar': 'عنابة',
                'website': 'https://www.univ-annaba.dz',
                'email': 'contact@univ-annaba.dz',
                'description': 'Université d\'Annaba',
                'specialties': [cs_specialty, ai_specialty],
            },
            {
                'name': 'Université Ferhat Abbas Sétif 1',
                'name_en': 'Ferhat Abbas Setif University 1',
                'name_ar': 'جامعة فرحات عباس سطيف 1',
                'acronym': 'UFAS1',
                'type': 'University',
                'city': 'Setif',
                'city_en': 'Setif',
                'city_ar': 'سطيف',
                'website': 'https://www.univ-setif.dz',
                'email': 'contact@univ-setif.dz',
                'description': 'Université de Sétif',
                'specialties': [cs_specialty],
            },
        ]

        created_count = 0
        for inst_data in institutions:
            specialties = inst_data.pop('specialties')
            
            institution, created = Institution.objects.get_or_create(
                acronym=inst_data['acronym'],
                defaults={
                    **inst_data,
                    'country': algeria,
                }
            )

            if created:
                institution.specialties.set(specialties)
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {institution.acronym} - {institution.name}'))
                created_count += 1
            else:
                # Update existing institution
                for key, value in inst_data.items():
                    setattr(institution, key, value)
                institution.country = algeria
                institution.save()
                institution.specialties.set(specialties)
                self.stdout.write(self.style.WARNING(f'⟳ Updated: {institution.acronym} - {institution.name}'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully processed {len(institutions)} institutions ({created_count} new)'))
        self.stdout.write(self.style.SUCCESS(f'Total institutions in database: {Institution.objects.count()}'))
