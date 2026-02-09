from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from resources.models import Course
from institutions.models import Institution
from datetime import date

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate courses in Arabic with real institutions'

    def handle(self, *args, **options):
        self.stdout.write('Creating courses...\n')
        
        # Get superuser as author
        author = User.objects.filter(is_superuser=True).first()
        if not author:
            self.stdout.write(self.style.WARNING('No superuser found. Please create a superuser first.'))
            return
        
        # Get institutions
        usthb = Institution.objects.filter(acronym='USTHB').first()
        esi = Institution.objects.filter(acronym='ESI').first()
        cerist = Institution.objects.filter(acronym='CERIST').first()
        univ_alg1 = Institution.objects.filter(acronym='UNIV-ALG1').first()
        
        if not any([usthb, esi, cerist, univ_alg1]):
            self.stdout.write(self.style.WARNING('No institutions found. Please run populate_algerian_institutions first.'))
            return

        # Courses data
        courses_data = [
            {
                'title': 'أساسيات معالجة اللغة العربية الطبيعية',
                'title_en': 'Fundamentals of Arabic Natural Language Processing',
                'title_ar': 'أساسيات معالجة اللغة العربية الطبيعية',
                'description': 'دورة تمهيدية شاملة في معالجة اللغة العربية الطبيعية تغطي المفاهيم الأساسية والتقنيات الحديثة في هذا المجال.',
                'language': 'ar',
                'field': 'nlp',
                'academic_level': 'master',
                'institution': usthb,
                'academic_year': '2024-2025',
                'keywords': 'NLP, معالجة اللغة, عربي, تعلم آلي',
            },
            {
                'title': 'الذكاء الاصطناعي وتطبيقاته',
                'title_en': 'Artificial Intelligence and Applications',
                'title_ar': 'الذكاء الاصطناعي وتطبيقاته',
                'description': 'دورة متقدمة في الذكاء الاصطناعي تركز على التطبيقات العملية والخوارزميات الحديثة في مجال الذكاء الاصطناعي.',
                'language': 'ar',
                'field': 'ai',
                'academic_level': 'master',
                'institution': esi,
                'academic_year': '2024-2025',
                'keywords': 'AI, ذكاء اصطناعي, تعلم عميق',
            },
            {
                'title': 'تحليل النصوص العربية',
                'title_en': 'Arabic Text Analysis',
                'title_ar': 'تحليل النصوص العربية',
                'description': 'دورة تطبيقية في تحليل النصوص العربية باستخدام تقنيات معالجة اللغة الطبيعية وتحليل المشاعر.',
                'language': 'ar',
                'field': 'text_mining',
                'academic_level': 'doctorate',
                'institution': usthb,
                'academic_year': '2024-2025',
                'keywords': 'تحليل نصوص, معالجة لغة, تحليل مشاعر',
            },
            {
                'title': 'التعلم الآلي المتقدم',
                'title_en': 'Advanced Machine Learning',
                'title_ar': 'التعلم الآلي المتقدم',
                'description': 'دورة متقدمة في التعلم الآلي تغطي الشبكات العصبية العميقة والتعلم المعزز وتطبيقاتها في معالجة اللغة.',
                'language': 'ar',
                'field': 'ml',
                'academic_level': 'doctorate',
                'institution': esi,
                'academic_year': '2024-2025',
                'keywords': 'machine learning, deep learning, neural networks',
            },
            {
                'title': 'اللسانيات الحاسوبية',
                'title_en': 'Computational Linguistics',
                'title_ar': 'اللسانيات الحاسوبية',
                'description': 'دورة في اللسانيات الحاسوبية تركز على التحليل الصرفي والنحوي للغة العربية باستخدام الحاسوب.',
                'language': 'ar',
                'field': 'comp_linguistics',
                'academic_level': 'master',
                'institution': univ_alg1,
                'academic_year': '2024-2025',
                'keywords': 'لسانيات, صرف, نحو, حاسوبية',
            },
            {
                'title': 'استخراج المعلومات من النصوص العربية',
                'title_en': 'Information Extraction from Arabic Texts',
                'title_ar': 'استخراج المعلومات من النصوص العربية',
                'description': 'دورة تطبيقية في استخراج المعلومات والكيانات المسماة من النصوص العربية.',
                'language': 'ar',
                'field': 'ir',
                'academic_level': 'master',
                'institution': cerist,
                'academic_year': '2024-2025',
                'keywords': 'استخراج معلومات, NER, information extraction',
            },
            {
                'title': 'الترجمة الآلية العربية-الإنجليزية',
                'title_en': 'Arabic-English Machine Translation',
                'title_ar': 'الترجمة الآلية العربية-الإنجليزية',
                'description': 'دورة متخصصة في بناء أنظمة الترجمة الآلية للغة العربية باستخدام الشبكات العصبية.',
                'language': 'ar',
                'field': 'translation',
                'academic_level': 'doctorate',
                'institution': usthb,
                'academic_year': '2024-2025',
                'keywords': 'ترجمة آلية, NMT, machine translation',
            },
            {
                'title': 'تحليل المشاعر في النصوص العربية',
                'title_en': 'Sentiment Analysis in Arabic Texts',
                'title_ar': 'تحليل المشاعر في النصوص العربية',
                'description': 'دورة في تحليل المشاعر والآراء في النصوص العربية باستخدام التعلم الآلي.',
                'language': 'ar',
                'field': 'sentiment_analysis',
                'academic_level': 'master',
                'institution': esi,
                'academic_year': '2024-2025',
                'keywords': 'sentiment analysis, تحليل مشاعر, opinion mining',
            },
        ]
        
        created_count = 0
        for course_data in courses_data:
            if course_data['institution'] is None:
                self.stdout.write(self.style.WARNING(f'⊘ Skipped: {course_data["title"]} (no institution)'))
                continue
                
            if not Course.objects.filter(title_en=course_data['title_en']).exists():
                Course.objects.create(
                    title=course_data['title'],
                    title_en=course_data['title_en'],
                    title_ar=course_data['title_ar'],
                    description=course_data['description'],
                    author=author,
                    teacher=author,
                    language=course_data['language'],
                    field=course_data['field'],
                    academic_level=course_data['academic_level'],
                    institution=course_data['institution'],
                    academic_year=course_data['academic_year'],
                    keywords=course_data['keywords']
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {course_data["title"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'⟳ Already exists: {course_data["title"]}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully created {created_count} courses'))
        self.stdout.write(self.style.SUCCESS(f'Total courses: {Course.objects.count()}'))
