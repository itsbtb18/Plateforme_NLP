from django.core.management.base import BaseCommand
from institutions.models import Specialty

class Command(BaseCommand):
    help = 'Populate specialties with Arabic and English names'

    def handle(self, *args, **kwargs):
        specialties = [
            # Sciences & Engineering
            {'code': 'CS', 'name_en': 'Computer Science', 'name_ar': 'علوم الحاسوب'},
            {'code': 'SE', 'name_en': 'Software Engineering', 'name_ar': 'هندسة البرمجيات'},
            {'code': 'AI', 'name_en': 'Artificial Intelligence', 'name_ar': 'الذكاء الاصطناعي'},
            {'code': 'DS', 'name_en': 'Data Science', 'name_ar': 'علم البيانات'},
            {'code': 'CYB', 'name_en': 'Cybersecurity', 'name_ar': 'الأمن السيبراني'},
            {'code': 'IS', 'name_en': 'Information Systems', 'name_ar': 'نظم المعلومات'},
            {'code': 'EE', 'name_en': 'Electrical Engineering', 'name_ar': 'الهندسة الكهربائية'},
            {'code': 'ME', 'name_en': 'Mechanical Engineering', 'name_ar': 'الهندسة الميكانيكية'},
            {'code': 'CE', 'name_en': 'Civil Engineering', 'name_ar': 'الهندسة المدنية'},
            {'code': 'CHE', 'name_en': 'Chemical Engineering', 'name_ar': 'الهندسة الكيميائية'},
            {'code': 'IE', 'name_en': 'Industrial Engineering', 'name_ar': 'الهندسة الصناعية'},
            {'code': 'AE', 'name_en': 'Aerospace Engineering', 'name_ar': 'هندسة الطيران'},
            {'code': 'BME', 'name_en': 'Biomedical Engineering', 'name_ar': 'الهندسة الطبية الحيوية'},
            {'code': 'ENV', 'name_en': 'Environmental Engineering', 'name_ar': 'الهندسة البيئية'},
            {'code': 'MATH', 'name_en': 'Mathematics', 'name_ar': 'الرياضيات'},
            {'code': 'PHYS', 'name_en': 'Physics', 'name_ar': 'الفيزياء'},
            {'code': 'CHEM', 'name_en': 'Chemistry', 'name_ar': 'الكيمياء'},
            {'code': 'BIO', 'name_en': 'Biology', 'name_ar': 'علم الأحياء'},
            {'code': 'BIOT', 'name_en': 'Biotechnology', 'name_ar': 'التكنولوجيا الحيوية'},
            
            # Medical & Health Sciences
            {'code': 'MED', 'name_en': 'Medicine', 'name_ar': 'الطب'},
            {'code': 'NURS', 'name_en': 'Nursing', 'name_ar': 'التمريض'},
            {'code': 'PHAR', 'name_en': 'Pharmacy', 'name_ar': 'الصيدلة'},
            {'code': 'DENT', 'name_en': 'Dentistry', 'name_ar': 'طب الأسنان'},
            {'code': 'PH', 'name_en': 'Public Health', 'name_ar': 'الصحة العامة'},
            {'code': 'VET', 'name_en': 'Veterinary Medicine', 'name_ar': 'الطب البيطري'},
            
            # Business & Economics
            {'code': 'BA', 'name_en': 'Business Administration', 'name_ar': 'إدارة الأعمال'},
            {'code': 'FIN', 'name_en': 'Finance', 'name_ar': 'المالية'},
            {'code': 'ACC', 'name_en': 'Accounting', 'name_ar': 'المحاسبة'},
            {'code': 'MKT', 'name_en': 'Marketing', 'name_ar': 'التسويق'},
            {'code': 'ECON', 'name_en': 'Economics', 'name_ar': 'الاقتصاد'},
            {'code': 'MGT', 'name_en': 'Management', 'name_ar': 'الإدارة'},
            {'code': 'IB', 'name_en': 'International Business', 'name_ar': 'الأعمال الدولية'},
            {'code': 'ENT', 'name_en': 'Entrepreneurship', 'name_ar': 'ريادة الأعمال'},
            
            # Social Sciences & Humanities
            {'code': 'PSY', 'name_en': 'Psychology', 'name_ar': 'علم النفس'},
            {'code': 'SOC', 'name_en': 'Sociology', 'name_ar': 'علم الاجتماع'},
            {'code': 'POLS', 'name_en': 'Political Science', 'name_ar': 'العلوم السياسية'},
            {'code': 'IR', 'name_en': 'International Relations', 'name_ar': 'العلاقات الدولية'},
            {'code': 'HIST', 'name_en': 'History', 'name_ar': 'التاريخ'},
            {'code': 'PHIL', 'name_en': 'Philosophy', 'name_ar': 'الفلسفة'},
            {'code': 'ANTH', 'name_en': 'Anthropology', 'name_ar': 'علم الإنسان'},
            {'code': 'GEO', 'name_en': 'Geography', 'name_ar': 'الجغرافيا'},
            
            # Law & Legal Studies
            {'code': 'LAW', 'name_en': 'Law', 'name_ar': 'القانون'},
            {'code': 'CJ', 'name_en': 'Criminal Justice', 'name_ar': 'العدالة الجنائية'},
            
            # Arts & Design
            {'code': 'ARCH', 'name_en': 'Architecture', 'name_ar': 'العمارة'},
            {'code': 'GD', 'name_en': 'Graphic Design', 'name_ar': 'التصميم الجرافيكي'},
            {'code': 'FA', 'name_en': 'Fine Arts', 'name_ar': 'الفنون الجميلة'},
            {'code': 'ID', 'name_en': 'Interior Design', 'name_ar': 'التصميم الداخلي'},
            {'code': 'FD', 'name_en': 'Fashion Design', 'name_ar': 'تصميم الأزياء'},
            
            # Communication & Media
            {'code': 'JOUR', 'name_en': 'Journalism', 'name_ar': 'الصحافة'},
            {'code': 'COMM', 'name_en': 'Communications', 'name_ar': 'الاتصالات'},
            {'code': 'MS', 'name_en': 'Media Studies', 'name_ar': 'دراسات الإعلام'},
            {'code': 'PR', 'name_en': 'Public Relations', 'name_ar': 'العلاقات العامة'},
            
            # Education
            {'code': 'EDU', 'name_en': 'Education', 'name_ar': 'التربية'},
            {'code': 'EDTECH', 'name_en': 'Educational Technology', 'name_ar': 'تكنولوجيا التعليم'},
            
            # Languages & Literature
            {'code': 'ENG', 'name_en': 'English Literature', 'name_ar': 'الأدب الإنجليزي'},
            {'code': 'ARA', 'name_en': 'Arabic Studies', 'name_ar': 'الدراسات العربية'},
            {'code': 'FRE', 'name_en': 'French Studies', 'name_ar': 'الدراسات الفرنسية'},
            {'code': 'LING', 'name_en': 'Linguistics', 'name_ar': 'اللسانيات'},
            
            # Agriculture & Food Science
            {'code': 'AGR', 'name_en': 'Agriculture', 'name_ar': 'الزراعة'},
            {'code': 'FS', 'name_en': 'Food Science', 'name_ar': 'علوم الأغذية'},
            
            # Other
            {'code': 'SPORT', 'name_en': 'Sports Science', 'name_ar': 'علوم الرياضة'},
            {'code': 'TH', 'name_en': 'Tourism & Hospitality', 'name_ar': 'السياحة والضيافة'},
            {'code': 'LIB', 'name_en': 'Library Science', 'name_ar': 'علم المكتبات'},
        ]
        
        created_count = 0
        for specialty_data in specialties:
            obj, created = Specialty.objects.get_or_create(
                code=specialty_data['code'],
                defaults={
                    'name_en': specialty_data['name_en'],
                    'name_ar': specialty_data['name_ar']
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully added {created_count} new specialties. Total: {Specialty.objects.count()}'
            )
        )