"""
Management command to clear existing data and populate with pending sample data.
Run with: python manage.py reset_and_populate_pending
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Clear existing data and populate with sample data in PENDING status for testing admin approval'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('⚠️  This will DELETE all existing resources, events, projects, topics, and institutions!'))
        
        # Clear existing data
        self._clear_data()
        
        # Get admin user
        admin_user = self._get_admin()
        if not admin_user:
            self.stdout.write(self.style.ERROR('No admin user found. Aborting.'))
            return
        
        # Populate in order of dependencies
        institutions = self._populate_institutions(admin_user)
        self._populate_documents(admin_user)
        self._populate_courses(admin_user, institutions)
        self._populate_corpora(admin_user)
        self._populate_tools(admin_user)
        self._populate_projects(admin_user, institutions)
        self._populate_events(admin_user, institutions)
        self._populate_forum_topics(admin_user)
        
        self.stdout.write(self.style.SUCCESS('\n✅ All sample data populated with PENDING status!'))
        self.stdout.write(self.style.NOTICE('You can now test the admin approval system.'))

    def _clear_data(self):
        """Clear all existing data from relevant models"""
        from resources.models import Document, Course, Corpus, NLPTool, Thesis, Memoir, Article
        from events.models import Event
        from projects.models import Project, ProjectMember
        from forum.models import Topic, ChatRoom, Message
        from institutions.models import Institution
        
        self.stdout.write('🗑️  Clearing existing data...')
        
        # Clear in reverse order of dependencies
        Message.objects.all().delete()
        self.stdout.write('  - Deleted all messages')
        
        ChatRoom.objects.all().delete()
        self.stdout.write('  - Deleted all chatrooms')
        
        Topic.objects.all().delete()
        self.stdout.write('  - Deleted all topics')
        
        ProjectMember.objects.all().delete()
        Project.objects.all().delete()
        self.stdout.write('  - Deleted all projects')
        
        Event.objects.all().delete()
        self.stdout.write('  - Deleted all events')
        
        # Documents and related
        Article.objects.all().delete()
        Thesis.objects.all().delete()
        Memoir.objects.all().delete()
        Document.objects.all().delete()
        self.stdout.write('  - Deleted all documents (articles, theses, memoirs)')
        
        Course.objects.all().delete()
        self.stdout.write('  - Deleted all courses')
        
        Corpus.objects.all().delete()
        self.stdout.write('  - Deleted all corpora')
        
        NLPTool.objects.all().delete()
        self.stdout.write('  - Deleted all NLP tools')
        
        Institution.objects.all().delete()
        self.stdout.write('  - Deleted all institutions')
        
        self.stdout.write(self.style.SUCCESS('  ✓ All data cleared\n'))

    def _get_admin(self):
        """Get an existing admin user"""
        admin = User.objects.filter(is_staff=True, is_superuser=True).first()
        if admin:
            self.stdout.write(f'Using admin: {admin.email}')
        return admin

    def _populate_institutions(self, admin_user):
        """Populate institutions with full bilingual data"""
        from institutions.models import Institution, Country, Specialty
        
        self.stdout.write('🏛️  Populating institutions...')
        
        countries = {c.code: c for c in Country.objects.all()}
        specialties = list(Specialty.objects.all())
        
        if not countries:
            self.stdout.write(self.style.WARNING('  No countries found. Run populate_countries first.'))
            return []
        
        institutions_data = [
            {
                'name': 'University of Algiers 1',
                'name_ar': 'جامعة الجزائر 1',
                'name_en': 'University of Algiers 1',
                'acronym': 'UA1',
                'type': 'University',
                'country_code': 'DZ',
                'city': 'Algiers',
                'city_ar': 'الجزائر العاصمة',
                'city_en': 'Algiers',
                'description_ar': 'جامعة الجزائر 1 هي أقدم وأعرق جامعة في الجزائر، تأسست عام 1909. تضم كليات متعددة تشمل العلوم الإنسانية والعلوم الدقيقة والحقوق.',
                'description_en': 'University of Algiers 1 is the oldest and most prestigious university in Algeria, founded in 1909. It includes multiple faculties covering humanities, exact sciences, and law.',
                'address_ar': 'شارع ديدوش مراد، الجزائر العاصمة',
                'address_en': '2, Didouche Mourad Street, Algiers',
            },
            {
                'name': 'USTHB',
                'name_ar': 'جامعة هواري بومدين للعلوم والتكنولوجيا',
                'name_en': 'University of Science and Technology Houari Boumediene',
                'acronym': 'USTHB',
                'type': 'University',
                'country_code': 'DZ',
                'city': 'Algiers',
                'city_ar': 'باب الزوار، الجزائر',
                'city_en': 'Bab Ezzouar, Algiers',
                'description_ar': 'جامعة هواري بومدين للعلوم والتكنولوجيا هي أكبر جامعة علمية في الجزائر، متخصصة في العلوم الدقيقة والتكنولوجيا والحاسوب.',
                'description_en': 'USTHB is the largest scientific university in Algeria, specializing in exact sciences, technology, and computer science.',
                'address_ar': 'باب الزوار، الجزائر العاصمة',
                'address_en': 'Bab Ezzouar, Algiers',
            },
            {
                'name': 'King Saud University',
                'name_ar': 'جامعة الملك سعود',
                'name_en': 'King Saud University',
                'acronym': 'KSU',
                'type': 'University',
                'country_code': 'SA',
                'city': 'Riyadh',
                'city_ar': 'الرياض',
                'city_en': 'Riyadh',
                'description_ar': 'جامعة الملك سعود هي أقدم جامعة في المملكة العربية السعودية، تأسست عام 1957. تعد من أفضل الجامعات في الشرق الأوسط.',
                'description_en': 'King Saud University is the oldest university in Saudi Arabia, founded in 1957. It is ranked among the top universities in the Middle East.',
                'address_ar': 'الدرعية، الرياض',
                'address_en': 'Diriyah, Riyadh',
            },
            {
                'name': 'Cairo University',
                'name_ar': 'جامعة القاهرة',
                'name_en': 'Cairo University',
                'acronym': 'CU',
                'type': 'University',
                'country_code': 'EG',
                'city': 'Cairo',
                'city_ar': 'القاهرة',
                'city_en': 'Cairo',
                'description_ar': 'جامعة القاهرة هي ثاني أقدم جامعة في مصر والعالم العربي، تأسست عام 1908. تضم أكثر من 200,000 طالب.',
                'description_en': 'Cairo University is the second oldest university in Egypt and the Arab world, founded in 1908. It has over 200,000 students.',
                'address_ar': 'الجيزة، القاهرة',
                'address_en': 'Giza, Cairo',
            },
            {
                'name': 'UAE University',
                'name_ar': 'جامعة الإمارات العربية المتحدة',
                'name_en': 'UAE University',
                'acronym': 'UAEU',
                'type': 'University',
                'country_code': 'AE',
                'city': 'Al Ain',
                'city_ar': 'العين',
                'city_en': 'Al Ain',
                'description_ar': 'جامعة الإمارات هي أول جامعة وطنية في دولة الإمارات، تأسست عام 1976. تعد مركزاً رائداً للبحث العلمي.',
                'description_en': 'UAE University is the first national university in the UAE, founded in 1976. It is a leading center for scientific research.',
                'address_ar': 'العين، أبوظبي',
                'address_en': 'Al Ain, Abu Dhabi',
            },
            {
                'name': 'CERIST Research Center',
                'name_ar': 'مركز البحث في الإعلام العلمي والتقني',
                'name_en': 'Research Center on Scientific and Technical Information',
                'acronym': 'CERIST',
                'type': 'Research Center',
                'country_code': 'DZ',
                'city': 'Algiers',
                'city_ar': 'بن عكنون، الجزائر',
                'city_en': 'Ben Aknoun, Algiers',
                'description_ar': 'مركز سيريست هو مركز بحثي رائد في الجزائر متخصص في تكنولوجيا المعلومات ومعالجة اللغة العربية.',
                'description_en': 'CERIST is a leading research center in Algeria specializing in information technology and Arabic language processing.',
                'address_ar': 'بن عكنون، الجزائر العاصمة',
                'address_en': 'Ben Aknoun, Algiers',
            },
        ]
        
        created_institutions = []
        for inst_data in institutions_data:
            country = countries.get(inst_data['country_code'])
            if not country:
                continue
            
            inst = Institution.objects.create(
                name=inst_data['name'],
                name_ar=inst_data['name_ar'],
                name_en=inst_data['name_en'],
                acronym=inst_data['acronym'],
                type=inst_data['type'],
                country=country,
                city=inst_data['city'],
                city_ar=inst_data['city_ar'],
                city_en=inst_data['city_en'],
                description=inst_data['description_en'],
                description_ar=inst_data['description_ar'],
                description_en=inst_data['description_en'],
                address_ar=inst_data['address_ar'],
                address_en=inst_data['address_en'],
                created_by=admin_user,
                website=f"https://www.{inst_data['acronym'].lower()}.edu",
                email=f"contact@{inst_data['acronym'].lower()}.edu",
            )
            if specialties:
                inst.specialties.set(random.sample(specialties, min(4, len(specialties))))
            created_institutions.append(inst)
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(created_institutions)} institutions'))
        return created_institutions

    def _populate_documents(self, admin_user):
        """Populate documents with PENDING status"""
        from resources.models import Document
        
        self.stdout.write('📄 Populating documents...')
        
        documents_data = [
            {
                'title': 'Arabic NER using Deep Learning',
                'title_ar': 'التعرف على الكيانات المسماة العربية باستخدام التعلم العميق',
                'title_en': 'Arabic Named Entity Recognition using Deep Learning',
                'description_ar': 'يقدم هذا البحث نظاماً متطوراً للتعرف على الكيانات المسماة في النصوص العربية باستخدام تقنيات التعلم العميق. يحقق النظام دقة 94% على مجموعة البيانات القياسية.',
                'description_en': 'This paper presents an advanced system for Named Entity Recognition in Arabic texts using deep learning techniques. The system achieves 94% accuracy on the standard benchmark dataset.',
                'type': 'article',
            },
            {
                'title': 'Sentiment Analysis for Arabic Social Media',
                'title_ar': 'تحليل المشاعر في وسائل التواصل الاجتماعي العربية',
                'title_en': 'Sentiment Analysis for Arabic Social Media',
                'description_ar': 'دراسة شاملة لتحليل المشاعر في منشورات وسائل التواصل الاجتماعي باللغة العربية، تشمل اللهجات المختلفة والعربية الفصحى الحديثة.',
                'description_en': 'A comprehensive study on sentiment analysis in Arabic social media posts, covering various dialects and Modern Standard Arabic.',
                'type': 'article',
            },
            {
                'title': 'Arabic Text Summarization Survey',
                'title_ar': 'مسح شامل لتلخيص النص العربي',
                'title_en': 'Arabic Text Summarization: A Comprehensive Survey',
                'description_ar': 'مسح شامل لتقنيات تلخيص النصوص العربية، يغطي الأساليب التقليدية والحديثة القائمة على الشبكات العصبية.',
                'description_en': 'A comprehensive survey of Arabic text summarization techniques, covering traditional approaches and modern neural network-based methods.',
                'type': 'article',
            },
            {
                'title': 'Neural Arabic Language Understanding',
                'title_ar': 'نهج عصبي لفهم اللغة العربية',
                'title_en': 'A Neural Approach to Arabic Language Understanding',
                'description_ar': 'أطروحة دكتوراه تقدم نموذجاً عصبياً جديداً لفهم اللغة العربية، مع تطبيقات على الإجابة على الأسئلة والاستدلال النصي.',
                'description_en': 'A doctoral thesis presenting a novel neural model for Arabic language understanding, with applications to question answering and textual entailment.',
                'type': 'thesis',
            },
            {
                'title': 'Arabic Chatbot Implementation',
                'title_ar': 'تنفيذ روبوت محادثة عربي باستخدام المحولات',
                'title_en': 'Implementing Arabic Chatbot using Transformers',
                'description_ar': 'مذكرة ماستر حول تنفيذ روبوت محادثة ذكي للغة العربية باستخدام نماذج المحولات مثل AraBERT.',
                'description_en': 'A master\'s thesis on implementing an intelligent Arabic chatbot using transformer models like AraBERT.',
                'type': 'memoir',
            },
            {
                'title': 'Cross-lingual Transfer for Arabic',
                'title_ar': 'التعلم عبر اللغات لمعالجة اللغة العربية',
                'title_en': 'Cross-lingual Transfer Learning for Arabic NLP',
                'description_ar': 'أطروحة دكتوراه تستكشف تقنيات نقل التعلم بين اللغات لتحسين أداء نماذج معالجة اللغة العربية.',
                'description_en': 'A doctoral thesis exploring cross-lingual transfer learning techniques to improve Arabic NLP model performance.',
                'type': 'thesis',
            },
        ]
        
        created_count = 0
        for doc_data in documents_data:
            Document.objects.create(
                title=doc_data['title'],
                title_ar=doc_data['title_ar'],
                title_en=doc_data['title_en'],
                document_type=doc_data['type'],
                file_format='PDF',
                description=doc_data['description_en'],
                description_ar=doc_data['description_ar'],
                description_en=doc_data['description_en'],
                author=admin_user,
                language=random.choice(['ar', 'en']),
                keywords='NLP, Arabic, Machine Learning, Deep Learning',
                approval_status='pending',
                views_count=0,
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} documents (PENDING)'))

    def _populate_courses(self, admin_user, institutions):
        """Populate courses with PENDING status"""
        from resources.models import Course
        
        self.stdout.write('📚 Populating courses...')
        
        if not institutions:
            self.stdout.write(self.style.WARNING('  No institutions. Skipping courses.'))
            return
        
        courses_data = [
            {
                'title': 'Introduction to NLP',
                'title_ar': 'مقدمة في معالجة اللغات الطبيعية',
                'title_en': 'Introduction to Natural Language Processing',
                'description_ar': 'مقرر أساسي يغطي مفاهيم معالجة اللغات الطبيعية، من التحليل الصرفي إلى التحليل الدلالي. يتضمن تطبيقات عملية بلغة بايثون.',
                'description_en': 'A foundational course covering NLP concepts from morphological to semantic analysis. Includes hands-on Python applications.',
                'level': 'bachelor',
                'field': 'nlp',
            },
            {
                'title': 'Advanced Arabic NLP',
                'title_ar': 'تقنيات متقدمة في معالجة اللغة العربية',
                'title_en': 'Advanced Arabic NLP Techniques',
                'description_ar': 'مقرر متقدم يركز على التحديات الخاصة باللغة العربية في معالجة اللغات الطبيعية، بما في ذلك التشكيل الآلي والتحليل الصرفي.',
                'description_en': 'An advanced course focusing on Arabic-specific challenges in NLP, including automatic diacritization and morphological analysis.',
                'level': 'master',
                'field': 'nlp',
            },
            {
                'title': 'Deep Learning for NLP',
                'title_ar': 'التعلم العميق لمعالجة اللغات',
                'title_en': 'Deep Learning for Natural Language Processing',
                'description_ar': 'مقرر دكتوراه يغطي أحدث تقنيات التعلم العميق المطبقة على معالجة اللغات، بما في ذلك نماذج المحولات وآلية الانتباه.',
                'description_en': 'A doctoral course covering state-of-the-art deep learning techniques applied to NLP, including transformers and attention mechanisms.',
                'level': 'doctorate',
                'field': 'ai',
            },
            {
                'title': 'Arabic Corpus Linguistics',
                'title_ar': 'لسانيات المدونات العربية',
                'title_en': 'Arabic Corpus Linguistics',
                'description_ar': 'دراسة اللغة العربية من خلال تحليل المدونات اللغوية الكبيرة. يشمل بناء المدونات وتحليلها إحصائياً.',
                'description_en': 'Study of Arabic language through analysis of large linguistic corpora. Includes corpus building and statistical analysis.',
                'level': 'master',
                'field': 'corpus_linguistics',
            },
            {
                'title': 'Machine Learning for Text',
                'title_ar': 'التعلم الآلي لتحليل النصوص',
                'title_en': 'Machine Learning for Text Analysis',
                'description_ar': 'تطبيق خوارزميات التعلم الآلي على تحليل النصوص، بما في ذلك التصنيف والتجميع واستخراج المعلومات.',
                'description_en': 'Application of machine learning algorithms to text analysis, including classification, clustering, and information extraction.',
                'level': 'master',
                'field': 'ml',
            },
        ]
        
        created_count = 0
        for course_data in courses_data:
            Course.objects.create(
                title=course_data['title'],
                title_ar=course_data['title_ar'],
                title_en=course_data['title_en'],
                description=course_data['description_en'],
                description_ar=course_data['description_ar'],
                description_en=course_data['description_en'],
                author=admin_user,
                teacher=admin_user,
                institution=random.choice(institutions),
                academic_level=course_data['level'],
                field=course_data['field'],
                academic_year='2025-2026',
                language=random.choice(['ar', 'en']),
                keywords='NLP, Arabic, Course, Education',
                approval_status='pending',
                views_count=0,
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} courses (PENDING)'))

    def _populate_corpora(self, admin_user):
        """Populate corpora with PENDING status"""
        from resources.models import Corpus
        
        self.stdout.write('📊 Populating corpora...')
        
        corpora_data = [
            {
                'title': 'Arabic News Corpus 2025',
                'title_ar': 'مدونة الأخبار العربية 2025',
                'title_en': 'Arabic News Corpus 2025',
                'description_ar': 'مدونة شاملة تضم أكثر من 500,000 مقال إخباري من مصادر عربية متنوعة، تغطي الفترة من 2020 إلى 2025.',
                'description_en': 'A comprehensive corpus containing over 500,000 news articles from various Arabic sources, covering 2020-2025.',
                'size': 500000,
                'format': 'json',
                'field': 'nlp',
            },
            {
                'title': 'Arabic Twitter Dataset',
                'title_ar': 'مجموعة بيانات تويتر العربية',
                'title_en': 'Arabic Twitter Dataset',
                'description_ar': 'مجموعة بيانات تضم مليون تغريدة عربية مع تصنيفات للمشاعر، تشمل لهجات مختلفة من العالم العربي.',
                'description_en': 'A dataset containing 1 million Arabic tweets with sentiment labels, including various dialects from across the Arab world.',
                'size': 1000000,
                'format': 'csv',
                'field': 'sentiment_analysis',
            },
            {
                'title': 'Moroccan Dialect Corpus',
                'title_ar': 'مدونة اللهجة المغربية',
                'title_en': 'Moroccan Dialect Corpus',
                'description_ar': 'مدونة متخصصة في اللهجة المغربية (الدارجة) تضم نصوصاً متنوعة من وسائل التواصل الاجتماعي والمحادثات.',
                'description_en': 'A specialized corpus for Moroccan dialect (Darija) containing diverse texts from social media and conversations.',
                'size': 250000,
                'format': 'txt',
                'field': 'arabic_linguistics',
            },
            {
                'title': 'Arabic Medical Corpus',
                'title_ar': 'مدونة النصوص الطبية العربية',
                'title_en': 'Arabic Medical Corpus',
                'description_ar': 'مدونة طبية تضم مقالات علمية وسجلات طبية مجهولة الهوية باللغة العربية لأغراض البحث في المعلوماتية الصحية.',
                'description_en': 'A medical corpus containing scientific articles and anonymized medical records in Arabic for health informatics research.',
                'size': 300000,
                'format': 'xml',
                'field': 'other',
            },
            {
                'title': 'Classical Arabic Literature',
                'title_ar': 'مدونة الأدب العربي الكلاسيكي',
                'title_en': 'Classical Arabic Literature Corpus',
                'description_ar': 'مجموعة من النصوص الأدبية العربية الكلاسيكية تشمل الشعر والنثر من العصر الجاهلي إلى العصر العباسي.',
                'description_en': 'A collection of classical Arabic literary texts including poetry and prose from pre-Islamic to Abbasid era.',
                'size': 400000,
                'format': 'txt',
                'field': 'arabic_linguistics',
            },
        ]
        
        created_count = 0
        for corpus_data in corpora_data:
            Corpus.objects.create(
                title=corpus_data['title'],
                title_ar=corpus_data['title_ar'],
                title_en=corpus_data['title_en'],
                description=corpus_data['description_en'],
                description_ar=corpus_data['description_ar'],
                description_en=corpus_data['description_en'],
                author=admin_user,
                size=corpus_data['size'],
                field=corpus_data['field'],
                file_format=corpus_data['format'],
                language='ar',
                keywords='Arabic, Corpus, NLP, Dataset',
                approval_status='pending',
                views_count=0,
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} corpora (PENDING)'))

    def _populate_tools(self, admin_user):
        """Populate NLP tools with PENDING status"""
        from resources.models import NLPTool
        
        self.stdout.write('🔧 Populating NLP tools...')
        
        tools_data = [
            {
                'title': 'ArabicBERT Pro',
                'title_ar': 'بيرت العربي برو',
                'title_en': 'ArabicBERT Pro',
                'description_ar': 'نموذج لغوي متقدم مبني على معمارية BERT مدرب على مليارات الكلمات العربية. يدعم مهام متعددة كالتصنيف والتعرف على الكيانات.',
                'description_en': 'An advanced language model based on BERT architecture trained on billions of Arabic words. Supports multiple tasks like classification and NER.',
                'type': 'ner',
                'url': 'https://huggingface.co/arabic-bert-pro',
            },
            {
                'title': 'Farasa 2.0',
                'title_ar': 'فراسة 2.0',
                'title_en': 'Farasa 2.0',
                'description_ar': 'الإصدار المحسن من أداة فراسة لتقطيع النص العربي. يتضمن تحسينات في الأداء ودعم للهجات العربية المختلفة.',
                'description_en': 'The improved version of Farasa Arabic segmentation tool. Includes performance improvements and support for various Arabic dialects.',
                'type': 'tokenization',
                'url': 'https://farasa.qcri.org/v2',
            },
            {
                'title': 'Arabic Sentiment Analyzer',
                'title_ar': 'محلل المشاعر العربي',
                'title_en': 'Arabic Sentiment Analyzer',
                'description_ar': 'أداة متخصصة في تحليل المشاعر للنصوص العربية، تدعم ثلاث درجات: إيجابي، سلبي، محايد. تعمل على النص الفصيح واللهجات.',
                'description_en': 'A specialized tool for Arabic sentiment analysis, supporting three classes: positive, negative, neutral. Works on MSA and dialects.',
                'type': 'sentiment_analysis',
                'url': 'https://github.com/arabic-nlp/sentiment',
            },
            {
                'title': 'Mishkal Diacritizer',
                'title_ar': 'مشكال للتشكيل',
                'title_en': 'Mishkal Arabic Diacritizer',
                'description_ar': 'أداة مفتوحة المصدر للتشكيل الآلي للنصوص العربية. تستخدم قواعد صرفية ونحوية لتحديد الحركات الصحيحة.',
                'description_en': 'An open-source tool for automatic diacritization of Arabic text. Uses morphological and grammatical rules to determine correct diacritics.',
                'type': 'tokenization',
                'url': 'https://github.com/linuxscout/mishkal',
            },
            {
                'title': 'Arabic POS Tagger',
                'title_ar': 'مصنف أقسام الكلام العربي',
                'title_en': 'Arabic Part-of-Speech Tagger',
                'description_ar': 'أداة لتصنيف أقسام الكلام في النصوص العربية باستخدام الشبكات العصبية المتكررة.',
                'description_en': 'A tool for tagging parts of speech in Arabic texts using recurrent neural networks.',
                'type': 'pos_tagging',
                'url': 'https://github.com/arabic-nlp/pos-tagger',
            },
        ]
        
        created_count = 0
        for tool_data in tools_data:
            NLPTool.objects.create(
                title=tool_data['title'],
                title_ar=tool_data['title_ar'],
                title_en=tool_data['title_en'],
                description=tool_data['description_en'],
                description_ar=tool_data['description_ar'],
                description_en=tool_data['description_en'],
                author=admin_user,
                tool_type=tool_data['type'],
                version='2.0.0',
                documentation_link=tool_data['url'],
                access_link=tool_data['url'],
                supported_languages='ar',
                keywords='Arabic, NLP, Tool',
                approval_status='pending',
                views_count=0,
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} NLP tools (PENDING)'))

    def _populate_projects(self, admin_user, institutions):
        """Populate projects with PENDING status"""
        from projects.models import Project
        
        self.stdout.write('🚀 Populating projects...')
        
        if not institutions:
            self.stdout.write(self.style.WARNING('  No institutions. Skipping projects.'))
            return
        
        projects_data = [
            {
                'title': 'Arabic AI Initiative',
                'title_ar': 'مبادرة الذكاء الاصطناعي العربي',
                'title_en': 'Arabic Artificial Intelligence Initiative',
                'description_ar': 'مشروع بحثي طموح يهدف إلى تطوير نماذج ذكاء اصطناعي متقدمة خاصة باللغة العربية، بالتعاون مع عدة جامعات عربية.',
                'description_en': 'An ambitious research project aimed at developing advanced AI models specific to Arabic language, in collaboration with several Arab universities.',
                'status': 'ongoing',
            },
            {
                'title': 'Dialectal Arabic NLP',
                'title_ar': 'معالجة اللهجات العربية آلياً',
                'title_en': 'Cross-dialectal Arabic NLP Project',
                'description_ar': 'مشروع يركز على تطوير أدوات معالجة اللغة الطبيعية قادرة على التعامل مع مختلف اللهجات العربية من المغرب إلى الخليج.',
                'description_en': 'A project focusing on developing NLP tools capable of handling various Arabic dialects from Morocco to the Gulf.',
                'status': 'ongoing',
            },
            {
                'title': 'Arabic Speech Recognition',
                'title_ar': 'نظام التعرف على الكلام العربي',
                'title_en': 'Arabic Speech-to-Text System',
                'description_ar': 'تطوير نظام متقدم للتعرف على الكلام العربي يدعم اللغة الفصحى واللهجات الرئيسية.',
                'description_en': 'Development of an advanced Arabic speech recognition system supporting MSA and major dialects.',
                'status': 'planned',
            },
            {
                'title': 'Arabic Heritage AI',
                'title_ar': 'الذكاء الاصطناعي للتراث العربي',
                'title_en': 'AI for Arabic Heritage Preservation',
                'description_ar': 'استخدام تقنيات الذكاء الاصطناعي لرقمنة وحفظ المخطوطات والنصوص التراثية العربية.',
                'description_en': 'Using AI technologies to digitize and preserve Arabic manuscripts and heritage texts.',
                'status': 'ongoing',
            },
            {
                'title': 'Arabic Medical NLP',
                'title_ar': 'معالجة النصوص الطبية العربية',
                'title_en': 'Arabic Medical Natural Language Processing',
                'description_ar': 'مشروع لتطوير أدوات معالجة اللغة الطبيعية للنصوص الطبية العربية لتحسين الرعاية الصحية.',
                'description_en': 'A project to develop NLP tools for Arabic medical texts to improve healthcare.',
                'status': 'planned',
            },
        ]
        
        created_count = 0
        for proj_data in projects_data:
            Project.objects.create(
                title=proj_data['title'],
                title_ar=proj_data['title_ar'],
                title_en=proj_data['title_en'],
                description=proj_data['description_en'],
                description_ar=proj_data['description_ar'],
                description_en=proj_data['description_en'],
                coordinator=admin_user,
                institution=random.choice(institutions),
                status=proj_data['status'],
                date_start=timezone.now().date() - timedelta(days=random.randint(30, 180)),
                approval_status='pending',
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} projects (PENDING)'))

    def _populate_events(self, admin_user, institutions):
        """Populate events with PENDING status"""
        from events.models import Event
        
        self.stdout.write('📅 Populating events...')
        
        if not institutions:
            self.stdout.write(self.style.WARNING('  No institutions. Skipping events.'))
            return
        
        events_data = [
            {
                'title': 'Arabic NLP Conference 2026',
                'title_ar': 'المؤتمر الدولي لمعالجة اللغة العربية 2026',
                'title_en': 'International Arabic NLP Conference 2026',
                'description_ar': 'المؤتمر السنوي الأكبر في مجال معالجة اللغة العربية الطبيعية. يجمع باحثين من جميع أنحاء العالم لعرض أحدث الأبحاث.',
                'description_en': 'The largest annual conference in Arabic NLP. Brings together researchers from around the world to present latest research.',
                'type': 'conference',
                'location_ar': 'دبي، الإمارات العربية المتحدة',
                'location_en': 'Dubai, United Arab Emirates',
            },
            {
                'title': 'Arabic Dialects Workshop',
                'title_ar': 'ورشة عمل اللهجات العربية',
                'title_en': 'Workshop on Arabic Dialects Processing',
                'description_ar': 'ورشة عمل متخصصة في معالجة اللهجات العربية المختلفة والتحديات التقنية المرتبطة بها.',
                'description_en': 'A specialized workshop on processing different Arabic dialects and related technical challenges.',
                'type': 'workshop',
                'location_ar': 'الدار البيضاء، المغرب',
                'location_en': 'Casablanca, Morocco',
            },
            {
                'title': 'Arabic AI Hackathon',
                'title_ar': 'هاكاثون الذكاء الاصطناعي العربي',
                'title_en': 'Arabic AI Hackathon 2026',
                'description_ar': 'مسابقة برمجية لتطوير حلول مبتكرة باستخدام الذكاء الاصطناعي للغة العربية. جوائز قيمة للفائزين.',
                'description_en': 'A programming competition to develop innovative AI solutions for Arabic language. Valuable prizes for winners.',
                'type': 'hackathon',
                'location_ar': 'الرياض، السعودية',
                'location_en': 'Riyadh, Saudi Arabia',
            },
            {
                'title': 'Arabic Morphology Seminar',
                'title_ar': 'ندوة الصرف العربي الحاسوبي',
                'title_en': 'Seminar on Computational Arabic Morphology',
                'description_ar': 'ندوة علمية تناقش أحدث التطورات في معالجة الصرف العربي حاسوبياً.',
                'description_en': 'A scientific seminar discussing the latest developments in computational Arabic morphology.',
                'type': 'seminar',
                'location_ar': 'القاهرة، مصر',
                'location_en': 'Cairo, Egypt',
            },
            {
                'title': 'Call for Papers: Arabic NLP Journal',
                'title_ar': 'دعوة للأبحاث: المجلة العربية لمعالجة اللغة',
                'title_en': 'Call for Papers: Journal of Arabic NLP',
                'description_ar': 'دعوة لتقديم الأبحاث للعدد الخاص بالمجلة العربية لمعالجة اللغات الطبيعية حول موضوع نماذج اللغة الكبيرة.',
                'description_en': 'Call for submissions to the special issue of Journal of Arabic NLP on Large Language Models.',
                'type': 'call_for_papers',
                'location_ar': 'عبر الإنترنت',
                'location_en': 'Online',
            },
        ]
        
        created_count = 0
        for event_data in events_data:
            start_date = timezone.now().date() + timedelta(days=random.randint(30, 180))
            Event.objects.create(
                title=event_data['title'],
                title_ar=event_data['title_ar'],
                title_en=event_data['title_en'],
                description=event_data['description_en'],
                description_ar=event_data['description_ar'],
                description_en=event_data['description_en'],
                event_type=event_data['type'],
                domains='nlp,ai,arabic_lang',
                location=event_data['location_en'],
                location_ar=event_data['location_ar'],
                location_en=event_data['location_en'],
                start_date=start_date,
                end_date=start_date + timedelta(days=random.randint(1, 5)),
                submission_deadline=start_date - timedelta(days=30),
                website='https://example.com/event',
                organizer=random.choice(institutions),
                contact_email='contact@event.org',
                created_by=admin_user,
                approval_status='pending',
                is_approved=False,
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} events (PENDING)'))

    def _populate_forum_topics(self, admin_user):
        """Populate forum topics with PENDING status"""
        from forum.models import Topic
        
        self.stdout.write('💬 Populating forum topics...')
        
        topics_data = [
            {
                'title': 'Best Practices for Arabic NER',
                'title_ar': 'أفضل الممارسات للتعرف على الكيانات المسماة العربية',
                'title_en': 'Best Practices for Arabic Named Entity Recognition',
                'description_ar': 'نقاش حول أفضل الممارسات والتقنيات للتعرف على الكيانات المسماة في النصوص العربية. شاركوا تجاربكم!',
                'description_en': 'Discussion on best practices and techniques for NER in Arabic texts. Share your experiences!',
            },
            {
                'title': 'AraBERT vs mBERT',
                'title_ar': 'مقارنة بين آرابيرت ومالتيبيرت',
                'title_en': 'AraBERT vs Multilingual BERT for Arabic',
                'description_ar': 'أيهما أفضل لمهام معالجة اللغة العربية: آرابيرت المتخصص أم النموذج متعدد اللغات؟',
                'description_en': 'Which is better for Arabic NLP tasks: specialized AraBERT or multilingual BERT?',
            },
            {
                'title': 'Handling Arabic Dialects',
                'title_ar': 'التعامل مع اللهجات العربية في المعالجة الآلية',
                'title_en': 'Handling Arabic Dialects in NLP Systems',
                'description_ar': 'كيف نتعامل مع تنوع اللهجات العربية في أنظمة معالجة اللغة الطبيعية؟',
                'description_en': 'How do we handle the diversity of Arabic dialects in NLP systems?',
            },
            {
                'title': 'Arabic OCR Challenges',
                'title_ar': 'تحديات التعرف الضوئي على الحروف العربية',
                'title_en': 'Challenges in Arabic Optical Character Recognition',
                'description_ar': 'مناقشة التحديات الخاصة بالتعرف الضوئي على النصوص العربية وحلولها.',
                'description_en': 'Discussion of Arabic-specific OCR challenges and solutions.',
            },
            {
                'title': 'Building Arabic Corpora',
                'title_ar': 'بناء المدونات اللغوية العربية',
                'title_en': 'Building Arabic Language Corpora',
                'description_ar': 'تبادل الخبرات حول بناء وتوثيق المدونات اللغوية العربية للأغراض البحثية.',
                'description_en': 'Sharing experiences on building and documenting Arabic corpora for research purposes.',
            },
        ]
        
        created_count = 0
        for topic_data in topics_data:
            Topic.objects.create(
                title=topic_data['title'],
                title_ar=topic_data['title_ar'],
                title_en=topic_data['title_en'],
                description=topic_data['description_en'],
                description_ar=topic_data['description_ar'],
                description_en=topic_data['description_en'],
                creator=admin_user,
                approval_status='pending',
                is_closed=False,
            )
            created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {created_count} forum topics (PENDING)'))
