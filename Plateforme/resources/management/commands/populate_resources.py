from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from resources.models import Corpus, NLPTool, Document, Course
from institutions.models import Institution
from datetime import date

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate resources with sample NLP data (bilingual)'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample resources...')
        
        # Get superuser as author
        author = User.objects.filter(is_superuser=True).first()
        if not author:
            self.stdout.write(self.style.WARNING('No superuser found to assign as author'))
            return
        
        # Create Corpora
        self.stdout.write('\n--- Creating Corpora ---')
        corpora_data = [
            {
                'title': 'مدونة الأخبار العربية',
                'title_en': 'Arabic News Corpus',
                'title_ar': 'مدونة الأخبار العربية',
                'description': 'مجموعة واسعة من المقالات الإخبارية العربية من مصادر متعددة تغطي مجالات متنوعة.',
                'language': 'ar',
                'size': 5000000,
                'field': 'nlp',
                'file_format': 'TXT',
                'keywords': 'news, arabic, journalism, media'
            },
            {
                'title': 'مجموعة بيانات وسائل التواصل الاجتماعي العربية',
                'title_en': 'Arabic Social Media Dataset',
                'title_ar': 'مجموعة بيانات وسائل التواصل الاجتماعي العربية',
                'description': 'مجموعة من التغريدات والمنشورات العربية على وسائل التواصل الاجتماعي لتحليل المشاعر ودراسة اللهجات.',
                'language': 'ar',
                'size': 1000000,
                'field': 'sentiment_analysis',
                'file_format': 'JSON',
                'keywords': 'social media, twitter, dialect, sentiment'
            },
            {
                'title': 'مدونة متوازية عربي-إنجليزي',
                'title_en': 'Parallel Arabic-English Corpus',
                'title_ar': 'مدونة متوازية عربي-إنجليزي',
                'description': 'مدونة متوازية للترجمة الآلية من العربية إلى الإنجليزية تحتوي على جمل محاذية.',
                'language': 'ar',
                'size': 500000,
                'field': 'translation',
                'file_format': 'TMX',
                'keywords': 'translation, parallel, bilingual, alignment'
            },
        ]
        
        corpus_count = 0
        for corpus_data in corpora_data:
            if not Corpus.objects.filter(title_en=corpus_data['title_en']).exists():
                Corpus.objects.create(
                    title=corpus_data['title'],
                    title_en=corpus_data['title_en'],
                    title_ar=corpus_data['title_ar'],
                    description=corpus_data['description'],
                    author=author,
                    language=corpus_data['language'],
                    size=corpus_data['size'],
                    field=corpus_data['field'],
                    file_format=corpus_data['file_format'],
                    keywords=corpus_data['keywords']
                )
                corpus_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created corpus: {corpus_data["title_en"]}'))
        
        # Create NLP Tools
        self.stdout.write('\n--- Creating NLP Tools ---')
        tools_data = [
            {
                'title': 'أداة تقسيم النصوص العربية',
                'title_en': 'Arabic Tokenizer',
                'title_ar': 'أداة تقسيم النصوص العربية',
                'description': 'أداة متقدمة لتقسيم النصوص العربية مع دعم الضمائم والصرف.',
                'language': 'ar',
                'tool_type': 'tokenization',
                'version': '1.0.0',
                'supported_languages': 'ar',
                'keywords': 'tokenization, morphology, segmentation'
            },
            {
                'title': 'أداة التعرف على الكيانات المسماة العربية',
                'title_en': 'Arabic Named Entity Recognizer',
                'title_ar': 'أداة التعرف على الكيانات المسماة العربية',
                'description': 'أداة للتعرف على الأشخاص والمواقع والمنظمات في النصوص العربية.',
                'language': 'ar',
                'tool_type': 'ner',
                'version': '2.1.0',
                'supported_languages': 'ar',
                'keywords': 'NER, entities, recognition, information extraction'
            },
            {
                'title': 'أداة وسم الكلام العربي',
                'title_en': 'Arabic Part-of-Speech Tagger',
                'title_ar': 'أداة وسم الكلام العربي',
                'description': 'أداة لوسم أجزاء الكلام العربي باستخدام نماذج عصبية متقدمة.',
                'language': 'ar',
                'tool_type': 'pos_tagging',
                'version': '1.5.2',
                'supported_languages': 'ar',
                'keywords': 'POS, tagging, morphology, syntax'
            },
        ]
        
        tool_count = 0
        for tool_data in tools_data:
            if not NLPTool.objects.filter(title_en=tool_data['title_en']).exists():
                NLPTool.objects.create(
                    title=tool_data['title'],
                    title_en=tool_data['title_en'],
                    title_ar=tool_data['title_ar'],
                    description=tool_data['description'],
                    author=author,
                    language=tool_data['language'],
                    tool_type=tool_data['tool_type'],
                    version=tool_data['version'],
                    supported_languages=tool_data['supported_languages'],
                    keywords=tool_data['keywords']
                )
                tool_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created tool: {tool_data["title_en"]}'))
        
        # Create Documents
        self.stdout.write('\n--- Creating Documents ---')
        documents_data = [
            {
                'title': 'مقدمة في معالجة اللغة العربية الطبيعية',
                'title_en': 'Introduction to Arabic NLP',
                'title_ar': 'مقدمة في معالجة اللغة العربية الطبيعية',
                'description': 'دليل شامل لمعالجة اللغة العربية الطبيعية يغطي المفاهيم والتقنيات الأساسية.',
                'language': 'ar',
                'document_type': 'article',
                'file_format': 'PDF',
                'keywords': 'NLP, tutorial, Arabic, introduction'
            },
            {
                'title': 'تحليل الصرف العربي',
                'title_en': 'Arabic Morphology Analysis',
                'title_ar': 'تحليل الصرف العربي',
                'description': 'بحث متعمق حول المناهج الحاسوبية لتحليل الصرف العربي.',
                'language': 'ar',
                'document_type': 'article',
                'file_format': 'PDF',
                'keywords': 'morphology, analysis, Arabic, computational linguistics'
            },
            {
                'title': 'الترجمة الآلية للعربية',
                'title_en': 'Machine Translation for Arabic',
                'title_ar': 'الترجمة الآلية للعربية',
                'description': 'ورقة مسحية حول أحدث التقنيات في أنظمة الترجمة الآلية العربية.',
                'language': 'ar',
                'document_type': 'article',
                'file_format': 'PDF',
                'keywords': 'machine translation, Arabic, neural networks, NMT'
            },
        ]
        
        doc_count = 0
        for doc_data in documents_data:
            if not Document.objects.filter(title_en=doc_data['title_en']).exists():
                Document.objects.create(
                    title=doc_data['title'],
                    title_en=doc_data['title_en'],
                    title_ar=doc_data['title_ar'],
                    description=doc_data['description'],
                    author=author,
                    language=doc_data['language'],
                    document_type=doc_data['document_type'],
                    file_format=doc_data['file_format'],
                    keywords=doc_data['keywords']
                )
                doc_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created document: {doc_data["title_en"]}'))
        
        # Create Courses
        self.stdout.write('\n--- Creating Courses ---')
        
        # Get an institution for courses
        institution = Institution.objects.first()
        if not institution:
            self.stdout.write(self.style.WARNING('No institution found. Skipping courses.'))
        else:
            courses_data = [
                {
                    'title': 'أساسيات معالجة اللغة العربية',
                    'title_en': 'Arabic NLP Fundamentals',
                    'title_ar': 'أساسيات معالجة اللغة العربية',
                    'description': 'دورة شاملة تغطي أساسيات معالجة اللغة العربية الطبيعية.',
                    'language': 'ar',
                    'field': 'nlp',
                    'academic_level': 'master',
                    'academic_year': '2023-2024',
                    'keywords': 'course, NLP, Arabic, fundamentals'
                },
                {
                    'title': 'تحليل النصوص العربية المتقدم',
                    'title_en': 'Advanced Arabic Text Analysis',
                    'title_ar': 'تحليل النصوص العربية المتقدم',
                    'description': 'دورة متقدمة حول تقنيات تحليل النصوص العربية بما في ذلك تحليل المشاعر ونمذجة المواضيع.',
                    'language': 'ar',
                    'field': 'text_mining',
                    'academic_level': 'doctorate',
                    'academic_year': '2023-2024',
                    'keywords': 'course, analysis, sentiment, advanced'
                },
            ]
            
            course_count = 0
            for course_data in courses_data:
                if not Course.objects.filter(title_en=course_data['title_en']).exists():
                    Course.objects.create(
                        title=course_data['title'],
                        title_en=course_data['title_en'],
                        title_ar=course_data['title_ar'],
                        description=course_data['description'],
                        author=author,
                        language=course_data['language'],
                        field=course_data['field'],
                        academic_level=course_data['academic_level'],
                        teacher=author,
                        institution=institution,
                        academic_year=course_data['academic_year'],
                        keywords=course_data['keywords']
                    )
                    course_count += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ Created course: {course_data["title_en"]}'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n=== Summary ==='))
        self.stdout.write(self.style.SUCCESS(f'Corpora: {corpus_count} new, Total: {Corpus.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'NLP Tools: {tool_count} new, Total: {NLPTool.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Documents: {doc_count} new, Total: {Document.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Courses: {course_count} new, Total: {Course.objects.count()}'))
