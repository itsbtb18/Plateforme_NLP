from django.core.management.base import BaseCommand
from institutions.models import Country

class Command(BaseCommand):
    help = 'Populate countries with Arabic and English names'

    def handle(self, *args, **kwargs):
        countries = [
            # Arab Countries
            {'code': 'DZ', 'name_en': 'Algeria', 'name_ar': 'الجزائر'},
            {'code': 'BH', 'name_en': 'Bahrain', 'name_ar': 'البحرين'},
            {'code': 'KM', 'name_en': 'Comoros', 'name_ar': 'جزر القمر'},
            {'code': 'DJ', 'name_en': 'Djibouti', 'name_ar': 'جيبوتي'},
            {'code': 'EG', 'name_en': 'Egypt', 'name_ar': 'مصر'},
            {'code': 'IQ', 'name_en': 'Iraq', 'name_ar': 'العراق'},
            {'code': 'JO', 'name_en': 'Jordan', 'name_ar': 'الأردن'},
            {'code': 'KW', 'name_en': 'Kuwait', 'name_ar': 'الكويت'},
            {'code': 'LB', 'name_en': 'Lebanon', 'name_ar': 'لبنان'},
            {'code': 'LY', 'name_en': 'Libya', 'name_ar': 'ليبيا'},
            {'code': 'MR', 'name_en': 'Mauritania', 'name_ar': 'موريتانيا'},
            {'code': 'MA', 'name_en': 'Morocco', 'name_ar': 'المغرب'},
            {'code': 'OM', 'name_en': 'Oman', 'name_ar': 'عمان'},
            {'code': 'PS', 'name_en': 'Palestine', 'name_ar': 'فلسطين'},
            {'code': 'QA', 'name_en': 'Qatar', 'name_ar': 'قطر'},
            {'code': 'SA', 'name_en': 'Saudi Arabia', 'name_ar': 'السعودية'},
            {'code': 'SO', 'name_en': 'Somalia', 'name_ar': 'الصومال'},
            {'code': 'SD', 'name_en': 'Sudan', 'name_ar': 'السودان'},
            {'code': 'SY', 'name_en': 'Syria', 'name_ar': 'سوريا'},
            {'code': 'TN', 'name_en': 'Tunisia', 'name_ar': 'تونس'},
            {'code': 'AE', 'name_en': 'United Arab Emirates', 'name_ar': 'الإمارات'},
            {'code': 'YE', 'name_en': 'Yemen', 'name_ar': 'اليمن'},
            
            # Major Western Countries
            {'code': 'US', 'name_en': 'United States', 'name_ar': 'الولايات المتحدة'},
            {'code': 'GB', 'name_en': 'United Kingdom', 'name_ar': 'المملكة المتحدة'},
            {'code': 'FR', 'name_en': 'France', 'name_ar': 'فرنسا'},
            {'code': 'DE', 'name_en': 'Germany', 'name_ar': 'ألمانيا'},
            {'code': 'IT', 'name_en': 'Italy', 'name_ar': 'إيطاليا'},
            {'code': 'ES', 'name_en': 'Spain', 'name_ar': 'إسبانيا'},
            {'code': 'CA', 'name_en': 'Canada', 'name_ar': 'كندا'},
            {'code': 'AU', 'name_en': 'Australia', 'name_ar': 'أستراليا'},
            {'code': 'NL', 'name_en': 'Netherlands', 'name_ar': 'هولندا'},
            {'code': 'BE', 'name_en': 'Belgium', 'name_ar': 'بلجيكا'},
            {'code': 'CH', 'name_en': 'Switzerland', 'name_ar': 'سويسرا'},
            {'code': 'SE', 'name_en': 'Sweden', 'name_ar': 'السويد'},
            {'code': 'NO', 'name_en': 'Norway', 'name_ar': 'النرويج'},
            {'code': 'DK', 'name_en': 'Denmark', 'name_ar': 'الدنمارك'},
            {'code': 'CN', 'name_en': 'China', 'name_ar': 'الصين'},
            {'code': 'JP', 'name_en': 'Japan', 'name_ar': 'اليابان'},
            {'code': 'IN', 'name_en': 'India', 'name_ar': 'الهند'},
            {'code': 'KR', 'name_en': 'South Korea', 'name_ar': 'كوريا الجنوبية'},
            {'code': 'TR', 'name_en': 'Turkey', 'name_ar': 'تركيا'},
            {'code': 'IR', 'name_en': 'Iran', 'name_ar': 'إيران'},
            {'code': 'PK', 'name_en': 'Pakistan', 'name_ar': 'باكستان'},
            {'code': 'ID', 'name_en': 'Indonesia', 'name_ar': 'إندونيسيا'},
            {'code': 'MY', 'name_en': 'Malaysia', 'name_ar': 'ماليزيا'},
            {'code': 'SG', 'name_en': 'Singapore', 'name_ar': 'سنغافورة'},
            {'code': 'BR', 'name_en': 'Brazil', 'name_ar': 'البرازيل'},
            {'code': 'MX', 'name_en': 'Mexico', 'name_ar': 'المكسيك'},
            {'code': 'ZA', 'name_en': 'South Africa', 'name_ar': 'جنوب أفريقيا'},
            {'code': 'RU', 'name_en': 'Russia', 'name_ar': 'روسيا'},
        ]
        
        created_count = 0
        for country_data in countries:
            obj, created = Country.objects.get_or_create(
                code=country_data['code'],
                defaults={
                    'name_en': country_data['name_en'],
                    'name_ar': country_data['name_ar']
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully added {created_count} new countries. Total: {Country.objects.count()}'
            )
        )
