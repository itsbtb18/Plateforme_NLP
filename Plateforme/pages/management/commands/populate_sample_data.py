"""
Management command to populate the database with sample data for all models.
Run with: python manage.py populate_sample_data
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random
import uuid

User = get_user_model()


class Command(BaseCommand):
    help = "Populate database with comprehensive sample data for all models"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("Starting to populate sample data..."))

        # Get or create admin user
        admin_user = self._get_or_create_admin()

        # Populate in order of dependencies
        institutions = self._populate_institutions(admin_user)
        self._populate_documents(admin_user)
        self._populate_courses(admin_user, institutions)
        self._populate_corpora(admin_user)
        self._populate_tools(admin_user)
        self._populate_projects(admin_user, institutions)
        self._populate_events(admin_user, institutions)
        self._populate_forum_topics(admin_user)
        self._populate_posts(admin_user)

        self.stdout.write(
            self.style.SUCCESS("✅ All sample data populated successfully!")
        )

    def _get_or_create_admin(self):
        """Get or create an admin user for sample data"""
        admin_email = "admin@nlp-platform.com"
        try:
            admin = User.objects.get(email=admin_email)
            self.stdout.write(f"  Using existing admin: {admin_email}")
        except User.DoesNotExist:
            admin = User.objects.create_superuser(
                email=admin_email, password="admin123", full_name="System Administrator"
            )
            admin.is_verified = True
            admin.save()
            self.stdout.write(
                self.style.SUCCESS(f"  Created admin user: {admin_email}")
            )
        return admin

    def _populate_institutions(self, admin_user):
        """Populate institutions"""
        from institutions.models import Institution, Country, Specialty

        self.stdout.write("  Populating institutions...")

        # Get countries and specialties
        countries = list(Country.objects.all())
        specialties = list(Specialty.objects.all())

        if not countries:
            self.stdout.write(
                self.style.WARNING(
                    "    No countries found. Run populate_countries first."
                )
            )
            return []

        institutions_data = [
            # Algeria
            {
                "name": "University of Algiers 1",
                "name_ar": "جامعة الجزائر 1",
                "acronym": "UA1",
                "type": "University",
                "country_code": "DZ",
                "city": "Algiers",
            },
            {
                "name": "University of Science and Technology Houari Boumediene",
                "name_ar": "جامعة هواري بومدين للعلوم والتكنولوجيا",
                "acronym": "USTHB",
                "type": "University",
                "country_code": "DZ",
                "city": "Algiers",
            },
            {
                "name": "University of Oran 1 Ahmed Ben Bella",
                "name_ar": "جامعة وهران 1 أحمد بن بلة",
                "acronym": "UO1",
                "type": "University",
                "country_code": "DZ",
                "city": "Oran",
            },
            {
                "name": "University of Constantine 1",
                "name_ar": "جامعة قسنطينة 1",
                "acronym": "UC1",
                "type": "University",
                "country_code": "DZ",
                "city": "Constantine",
            },
            {
                "name": "CERIST Research Center",
                "name_ar": "مركز البحث في الإعلام العلمي والتقني",
                "acronym": "CERIST",
                "type": "Research Center",
                "country_code": "DZ",
                "city": "Algiers",
            },
            # Saudi Arabia
            {
                "name": "King Saud University",
                "name_ar": "جامعة الملك سعود",
                "acronym": "KSU",
                "type": "University",
                "country_code": "SA",
                "city": "Riyadh",
            },
            {
                "name": "King Abdulaziz University",
                "name_ar": "جامعة الملك عبدالعزيز",
                "acronym": "KAU",
                "type": "University",
                "country_code": "SA",
                "city": "Jeddah",
            },
            {
                "name": "KAUST",
                "name_ar": "جامعة الملك عبدالله للعلوم والتقنية",
                "acronym": "KAUST",
                "type": "University",
                "country_code": "SA",
                "city": "Thuwal",
            },
            # Egypt
            {
                "name": "Cairo University",
                "name_ar": "جامعة القاهرة",
                "acronym": "CU",
                "type": "University",
                "country_code": "EG",
                "city": "Cairo",
            },
            {
                "name": "Alexandria University",
                "name_ar": "جامعة الإسكندرية",
                "acronym": "AU",
                "type": "University",
                "country_code": "EG",
                "city": "Alexandria",
            },
            {
                "name": "Ain Shams University",
                "name_ar": "جامعة عين شمس",
                "acronym": "ASU",
                "type": "University",
                "country_code": "EG",
                "city": "Cairo",
            },
            # UAE
            {
                "name": "UAE University",
                "name_ar": "جامعة الإمارات العربية المتحدة",
                "acronym": "UAEU",
                "type": "University",
                "country_code": "AE",
                "city": "Al Ain",
            },
            {
                "name": "Khalifa University",
                "name_ar": "جامعة خليفة",
                "acronym": "KU",
                "type": "University",
                "country_code": "AE",
                "city": "Abu Dhabi",
            },
            # Morocco
            {
                "name": "Mohammed V University",
                "name_ar": "جامعة محمد الخامس",
                "acronym": "UM5",
                "type": "University",
                "country_code": "MA",
                "city": "Rabat",
            },
            {
                "name": "Hassan II University",
                "name_ar": "جامعة الحسن الثاني",
                "acronym": "UH2",
                "type": "University",
                "country_code": "MA",
                "city": "Casablanca",
            },
            # Tunisia
            {
                "name": "University of Tunis El Manar",
                "name_ar": "جامعة تونس المنار",
                "acronym": "UTM",
                "type": "University",
                "country_code": "TN",
                "city": "Tunis",
            },
            {
                "name": "University of Sfax",
                "name_ar": "جامعة صفاقس",
                "acronym": "US",
                "type": "University",
                "country_code": "TN",
                "city": "Sfax",
            },
            # Jordan
            {
                "name": "University of Jordan",
                "name_ar": "الجامعة الأردنية",
                "acronym": "UJ",
                "type": "University",
                "country_code": "JO",
                "city": "Amman",
            },
            {
                "name": "Jordan University of Science and Technology",
                "name_ar": "جامعة العلوم والتكنولوجيا الأردنية",
                "acronym": "JUST",
                "type": "University",
                "country_code": "JO",
                "city": "Irbid",
            },
            # International
            {
                "name": "Stanford University",
                "name_ar": "جامعة ستانفورد",
                "acronym": "Stanford",
                "type": "University",
                "country_code": "US",
                "city": "Stanford",
            },
            {
                "name": "MIT",
                "name_ar": "معهد ماساتشوستس للتكنولوجيا",
                "acronym": "MIT",
                "type": "University",
                "country_code": "US",
                "city": "Cambridge",
            },
            {
                "name": "Oxford University",
                "name_ar": "جامعة أكسفورد",
                "acronym": "Oxford",
                "type": "University",
                "country_code": "GB",
                "city": "Oxford",
            },
            {
                "name": "Cambridge University",
                "name_ar": "جامعة كامبريدج",
                "acronym": "Cambridge",
                "type": "University",
                "country_code": "GB",
                "city": "Cambridge",
            },
            {
                "name": "Sorbonne University",
                "name_ar": "جامعة السوربون",
                "acronym": "Sorbonne",
                "type": "University",
                "country_code": "FR",
                "city": "Paris",
            },
        ]

        created_institutions = []
        created_count = 0
        for inst_data in institutions_data:
            try:
                country = Country.objects.get(code=inst_data["country_code"])
            except Country.DoesNotExist:
                continue

            inst, created = Institution.objects.get_or_create(
                name=inst_data["name"],
                defaults={
                    "name_ar": inst_data["name_ar"],
                    "name_en": inst_data["name"],
                    "acronym": inst_data["acronym"],
                    "type": inst_data["type"],
                    "country": country,
                    "city": inst_data["city"],
                    "created_by": admin_user,
                    "website": f"https://www.{inst_data['acronym'].lower()}.edu",
                    "email": f"contact@{inst_data['acronym'].lower()}.edu",
                    "description": f"Leading institution in NLP and Arabic language research.",
                },
            )
            created_institutions.append(inst)
            if created:
                # Add random specialties
                if specialties:
                    random_specialties = random.sample(
                        specialties, min(5, len(specialties))
                    )
                    inst.specialties.set(random_specialties)
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"    Created {created_count} institutions")
        )
        return created_institutions

    def _populate_documents(self, admin_user):
        """Populate documents (articles, theses, memoirs)"""
        from resources.models import Document

        self.stdout.write("  Populating documents...")

        articles_data = [
            {
                "title": "Arabic Named Entity Recognition using Deep Learning",
                "title_ar": "التعرف على الكيانات المسماة العربية باستخدام التعلم العميق",
                "type": "article",
            },
            {
                "title": "Sentiment Analysis for Arabic Social Media",
                "title_ar": "تحليل المشاعر في وسائل التواصل الاجتماعي العربية",
                "type": "article",
            },
            {
                "title": "Arabic Text Summarization: A Comprehensive Survey",
                "title_ar": "تلخيص النص العربي: مسح شامل",
                "type": "article",
            },
            {
                "title": "Machine Translation from Arabic to English",
                "title_ar": "الترجمة الآلية من العربية إلى الإنجليزية",
                "type": "article",
            },
            {
                "title": "Arabic Speech Recognition in Noisy Environments",
                "title_ar": "التعرف على الكلام العربي في البيئات الصاخبة",
                "type": "article",
            },
            {
                "title": "Dialectal Arabic Processing: Challenges and Solutions",
                "title_ar": "معالجة اللهجات العربية: التحديات والحلول",
                "type": "article",
            },
            {
                "title": "Arabic Question Answering Systems",
                "title_ar": "أنظمة الإجابة على الأسئلة العربية",
                "type": "article",
            },
            {
                "title": "Morphological Analysis of Arabic Text",
                "title_ar": "التحليل الصرفي للنص العربي",
                "type": "article",
            },
            {
                "title": "Arabic Word Embeddings: A Comparative Study",
                "title_ar": "تمثيل الكلمات العربية: دراسة مقارنة",
                "type": "article",
            },
            {
                "title": "Deep Learning for Arabic OCR",
                "title_ar": "التعلم العميق للتعرف الضوئي على الحروف العربية",
                "type": "article",
            },
        ]

        theses_data = [
            {
                "title": "A Neural Approach to Arabic Language Understanding",
                "title_ar": "نهج عصبي لفهم اللغة العربية",
                "type": "thesis",
            },
            {
                "title": "Cross-lingual Transfer Learning for Arabic NLP",
                "title_ar": "التعلم عبر اللغات لمعالجة اللغة العربية",
                "type": "thesis",
            },
            {
                "title": "Building Large-Scale Arabic Corpora",
                "title_ar": "بناء مدونات عربية واسعة النطاق",
                "type": "thesis",
            },
            {
                "title": "Arabic Information Retrieval Systems",
                "title_ar": "أنظمة استرجاع المعلومات العربية",
                "type": "thesis",
            },
            {
                "title": "Automatic Arabic Diacritization",
                "title_ar": "التشكيل الآلي للنص العربي",
                "type": "thesis",
            },
        ]

        memoirs_data = [
            {
                "title": "Implementing Arabic Chatbot using Transformers",
                "title_ar": "تنفيذ روبوت محادثة عربي باستخدام المحولات",
                "type": "memoir",
            },
            {
                "title": "Arabic Text Classification for News Articles",
                "title_ar": "تصنيف النصوص العربية للمقالات الإخبارية",
                "type": "memoir",
            },
            {
                "title": "Sentiment Analysis of Arabic Product Reviews",
                "title_ar": "تحليل مشاعر مراجعات المنتجات العربية",
                "type": "memoir",
            },
            {
                "title": "Arabic Spell Checker Development",
                "title_ar": "تطوير مدقق إملائي عربي",
                "type": "memoir",
            },
            {
                "title": "Named Entity Recognition in Arabic Medical Texts",
                "title_ar": "التعرف على الكيانات في النصوص الطبية العربية",
                "type": "memoir",
            },
        ]

        all_docs = articles_data + theses_data + memoirs_data
        created_count = 0

        for doc_data in all_docs:
            doc, created = Document.objects.get_or_create(
                title=doc_data["title"],
                defaults={
                    "title_ar": doc_data["title_ar"],
                    "title_en": doc_data["title"],
                    "document_type": doc_data["type"],
                    "file_format": "PDF",
                    "description": f"This is a research {doc_data['type']} about {doc_data['title']}. It contributes to the advancement of Arabic NLP research.",
                    "author": admin_user,
                    "language": random.choice(["ar", "en"]),
                    "keywords": "NLP, Arabic, Machine Learning, Deep Learning",
                    "approval_status": "approved",
                    "views_count": random.randint(10, 500),
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"    Created {created_count} documents"))

    def _populate_courses(self, admin_user, institutions):
        """Populate courses"""
        from resources.models import Course

        self.stdout.write("  Populating courses...")

        if not institutions:
            self.stdout.write(
                self.style.WARNING("    No institutions found. Skipping courses.")
            )
            return

        courses_data = [
            {
                "title": "Introduction to Natural Language Processing",
                "title_ar": "مقدمة في معالجة اللغات الطبيعية",
                "level": "bachelor",
                "field": "nlp",
            },
            {
                "title": "Advanced Arabic NLP Techniques",
                "title_ar": "تقنيات متقدمة في معالجة اللغة العربية",
                "level": "master",
                "field": "nlp",
            },
            {
                "title": "Machine Learning for Text Analysis",
                "title_ar": "التعلم الآلي لتحليل النصوص",
                "level": "master",
                "field": "ml",
            },
            {
                "title": "Deep Learning for NLP",
                "title_ar": "التعلم العميق لمعالجة اللغات",
                "level": "doctorate",
                "field": "ai",
            },
            {
                "title": "Arabic Corpus Linguistics",
                "title_ar": "لسانيات المدونات العربية",
                "level": "master",
                "field": "corpus_linguistics",
            },
            {
                "title": "Speech Recognition Fundamentals",
                "title_ar": "أساسيات التعرف على الكلام",
                "level": "bachelor",
                "field": "speech_processing",
            },
            {
                "title": "Text Mining and Information Extraction",
                "title_ar": "التنقيب في النصوص واستخراج المعلومات",
                "level": "master",
                "field": "text_mining",
            },
            {
                "title": "Transformer Models for Arabic",
                "title_ar": "نماذج المحولات للغة العربية",
                "level": "doctorate",
                "field": "ai",
            },
            {
                "title": "Arabic Sentiment Analysis Workshop",
                "title_ar": "ورشة تحليل المشاعر العربية",
                "level": "master",
                "field": "sentiment_analysis",
            },
            {
                "title": "Building Arabic Chatbots",
                "title_ar": "بناء روبوتات المحادثة العربية",
                "level": "bachelor",
                "field": "nlp",
            },
            {
                "title": "Python for NLP Beginners",
                "title_ar": "بايثون لمعالجة اللغات للمبتدئين",
                "level": "bachelor",
                "field": "computer_science",
            },
            {
                "title": "Arabic Named Entity Recognition",
                "title_ar": "التعرف على الكيانات المسماة العربية",
                "level": "master",
                "field": "named_entity",
            },
        ]

        created_count = 0
        for course_data in courses_data:
            course, created = Course.objects.get_or_create(
                title=course_data["title"],
                defaults={
                    "title_ar": course_data["title_ar"],
                    "title_en": course_data["title"],
                    "description": f"This course covers {course_data['title']}. Learn the latest techniques and best practices.",
                    "author": admin_user,
                    "teacher": admin_user,
                    "institution": random.choice(institutions),
                    "academic_level": course_data["level"],
                    "field": course_data["field"],
                    "academic_year": "2024-2025",
                    "language": random.choice(["ar", "en"]),
                    "keywords": "NLP, Arabic, Course, Learning",
                    "approval_status": "approved",
                    "views_count": random.randint(50, 1000),
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"    Created {created_count} courses"))

    def _populate_corpora(self, admin_user):
        """Populate corpora"""
        from resources.models import Corpus

        self.stdout.write("  Populating corpora...")

        corpora_data = [
            {
                "title": "Arabic News Corpus",
                "title_ar": "مدونة الأخبار العربية",
                "field": "nlp",
            },
            {
                "title": "Arabic Wikipedia Dump",
                "title_ar": "تفريغ ويكيبيديا العربية",
                "field": "corpus_linguistics",
            },
            {
                "title": "Arabic Twitter Dataset",
                "title_ar": "مجموعة بيانات تويتر العربية",
                "field": "sentiment_analysis",
            },
            {
                "title": "Arabic Sentiment Corpus",
                "title_ar": "مدونة المشاعر العربية",
                "field": "sentiment_analysis",
            },
            {
                "title": "Modern Standard Arabic Corpus",
                "title_ar": "مدونة العربية الفصحى الحديثة",
                "field": "arabic_linguistics",
            },
            {
                "title": "Dialectal Arabic Dataset (Levantine)",
                "title_ar": "مجموعة بيانات اللهجة الشامية",
                "field": "arabic_linguistics",
            },
            {
                "title": "Dialectal Arabic Dataset (Egyptian)",
                "title_ar": "مجموعة بيانات اللهجة المصرية",
                "field": "arabic_linguistics",
            },
            {
                "title": "Dialectal Arabic Dataset (Gulf)",
                "title_ar": "مجموعة بيانات اللهجة الخليجية",
                "field": "arabic_linguistics",
            },
            {
                "title": "Arabic Named Entity Dataset",
                "title_ar": "مجموعة بيانات الكيانات المسماة العربية",
                "field": "named_entity",
            },
            {
                "title": "Arabic-English Parallel Corpus",
                "title_ar": "المدونة المتوازية العربية-الإنجليزية",
                "field": "translation",
            },
            {
                "title": "Classical Arabic Texts Corpus",
                "title_ar": "مدونة النصوص العربية الكلاسيكية",
                "field": "arabic_linguistics",
            },
            {
                "title": "Arabic Medical Corpus",
                "title_ar": "مدونة النصوص الطبية العربية",
                "field": "other",
            },
        ]

        created_count = 0
        for corpus_data in corpora_data:
            corpus, created = Corpus.objects.get_or_create(
                title=corpus_data["title"],
                defaults={
                    "title_ar": corpus_data["title_ar"],
                    "title_en": corpus_data["title"],
                    "description": f"{corpus_data['title']} - A comprehensive Arabic language resource for NLP research.",
                    "author": admin_user,
                    "field": corpus_data["field"],
                    "language": "ar",
                    "keywords": "Arabic, Corpus, NLP, Dataset",
                    "approval_status": "approved",
                    "views_count": random.randint(100, 2000),
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"    Created {created_count} corpora"))

    def _populate_tools(self, admin_user):
        """Populate NLP tools"""
        from resources.models import NLPTool

        self.stdout.write("  Populating NLP tools...")

        tools_data = [
            {
                "title": "ArabicBERT",
                "title_ar": "بيرت العربي",
                "type": "ner",
                "url": "https://huggingface.co/asafaya/bert-base-arabic",
            },
            {
                "title": "CAMeL Tools",
                "title_ar": "أدوات كامل",
                "type": "tokenization",
                "url": "https://github.com/CAMeL-Lab/camel_tools",
            },
            {
                "title": "Farasa",
                "title_ar": "فراسة",
                "type": "tokenization",
                "url": "https://farasa.qcri.org/",
            },
            {
                "title": "MADAMIRA",
                "title_ar": "مداميرا",
                "type": "pos_tagging",
                "url": "https://camel.abudhabi.nyu.edu/madamira/",
            },
            {
                "title": "Stanford Arabic Parser",
                "title_ar": "محلل ستانفورد العربي",
                "type": "pos_tagging",
                "url": "https://nlp.stanford.edu/software/lex-parser.shtml",
            },
            {
                "title": "AraBERT",
                "title_ar": "آرابيرت",
                "type": "sentiment_analysis",
                "url": "https://github.com/aub-mind/arabert",
            },
            {
                "title": "Qalsadi",
                "title_ar": "قلسادي",
                "type": "stemming",
                "url": "https://github.com/linuxscout/qalsadi",
            },
            {
                "title": "Mishkal",
                "title_ar": "مشكال",
                "type": "tokenization",
                "url": "https://github.com/linuxscout/mishkal",
            },
            {
                "title": "Tashkeela",
                "title_ar": "تشكيلة",
                "type": "tokenization",
                "url": "https://github.com/linuxscout/tashkeela",
            },
            {
                "title": "Arabic WordNet",
                "title_ar": "شبكة الكلمات العربية",
                "type": "ner",
                "url": "https://globalwordnet.github.io/arabic-wordnet/",
            },
            {
                "title": "AraVec",
                "title_ar": "آرافيك",
                "type": "ner",
                "url": "https://github.com/bakrianoo/aravec",
            },
            {
                "title": "Arabic NMT Model",
                "title_ar": "نموذج الترجمة الآلية العربية",
                "type": "machine_translation",
                "url": "https://github.com/deep-spin/translation",
            },
        ]

        created_count = 0
        for tool_data in tools_data:
            tool, created = NLPTool.objects.get_or_create(
                title=tool_data["title"],
                defaults={
                    "title_ar": tool_data["title_ar"],
                    "title_en": tool_data["title"],
                    "description": f"{tool_data['title']} is a powerful NLP tool for Arabic language processing. It provides state-of-the-art performance for various NLP tasks.",
                    "author": admin_user,
                    "tool_type": tool_data["type"],
                    "version": "1.0.0",
                    "documentation_link": tool_data["url"],
                    "supported_languages": "ar",
                    "keywords": f"Arabic, NLP, {tool_data['type']}, Tool",
                    "approval_status": "approved",
                    "views_count": random.randint(200, 3000),
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"    Created {created_count} NLP tools"))

    def _populate_projects(self, admin_user, institutions):
        """Populate research projects"""
        from projects.models import Project

        self.stdout.write("  Populating projects...")

        if not institutions:
            self.stdout.write(
                self.style.WARNING("    No institutions found. Skipping projects.")
            )
            return

        projects_data = [
            {
                "title": "Arabic Language Understanding Initiative",
                "title_ar": "مبادرة فهم اللغة العربية",
                "status": "ongoing",
            },
            {
                "title": "Cross-dialectal Arabic NLP",
                "title_ar": "معالجة اللهجات العربية المتقاطعة",
                "status": "ongoing",
            },
            {
                "title": "Arabic Speech-to-Text System",
                "title_ar": "نظام تحويل الكلام إلى نص عربي",
                "status": "ongoing",
            },
            {
                "title": "Arabic Semantic Web Resources",
                "title_ar": "موارد الويب الدلالي العربي",
                "status": "completed",
            },
            {
                "title": "Arabic Educational Technology",
                "title_ar": "تكنولوجيا التعليم العربية",
                "status": "ongoing",
            },
            {
                "title": "Arabic Medical NLP",
                "title_ar": "معالجة النصوص الطبية العربية",
                "status": "ongoing",
            },
            {
                "title": "Arabic Legal Document Analysis",
                "title_ar": "تحليل الوثائق القانونية العربية",
                "status": "planned",
            },
            {
                "title": "Arabic Fake News Detection",
                "title_ar": "كشف الأخبار المزيفة العربية",
                "status": "ongoing",
            },
            {
                "title": "Arabic Heritage Digitization",
                "title_ar": "رقمنة التراث العربي",
                "status": "completed",
            },
            {
                "title": "Arabic Accessibility Tools",
                "title_ar": "أدوات إمكانية الوصول العربية",
                "status": "planned",
            },
        ]

        created_count = 0
        for proj_data in projects_data:
            project, created = Project.objects.get_or_create(
                title=proj_data["title"],
                defaults={
                    "title_ar": proj_data["title_ar"],
                    "title_en": proj_data["title"],
                    "description": f"{proj_data['title']} is a collaborative research project focused on advancing Arabic language technology.",
                    "coordinator": admin_user,
                    "institution": random.choice(institutions),
                    "status": proj_data["status"],
                    "date_start": timezone.now().date()
                    - timedelta(days=random.randint(30, 365)),
                    "approval_status": "approved",
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"    Created {created_count} projects"))

    def _populate_events(self, admin_user, institutions):
        """Populate events"""
        from events.models import Event

        self.stdout.write("  Populating events...")

        if not institutions:
            self.stdout.write(
                self.style.WARNING("    No institutions found. Skipping events.")
            )
            return

        events_data = [
            {
                "title": "Arabic NLP Conference 2026",
                "title_ar": "مؤتمر معالجة اللغة العربية 2026",
                "type": "conference",
            },
            {
                "title": "Workshop on Arabic Dialects",
                "title_ar": "ورشة عمل حول اللهجات العربية",
                "type": "workshop",
            },
            {
                "title": "Arabic AI Hackathon",
                "title_ar": "هاكاثون الذكاء الاصطناعي العربي",
                "type": "hackathon",
            },
            {
                "title": "Seminar on Arabic Morphology",
                "title_ar": "ندوة حول الصرف العربي",
                "type": "seminar",
            },
            {
                "title": "Call for Papers: Arabic NLP Journal",
                "title_ar": "دعوة للأبحاث: مجلة معالجة اللغة العربية",
                "type": "call_for_papers",
            },
            {
                "title": "Arabic Speech Processing Workshop",
                "title_ar": "ورشة معالجة الكلام العربي",
                "type": "workshop",
            },
            {
                "title": "International Arabic Language Day",
                "title_ar": "اليوم العالمي للغة العربية",
                "type": "conference",
            },
            {
                "title": "Arabic Machine Translation Summit",
                "title_ar": "قمة الترجمة الآلية العربية",
                "type": "conference",
            },
        ]

        created_count = 0
        for i, event_data in enumerate(events_data):
            start_date = timezone.now().date() + timedelta(days=30 + i * 15)
            event, created = Event.objects.get_or_create(
                title=event_data["title"],
                defaults={
                    "title_ar": event_data["title_ar"],
                    "title_en": event_data["title"],
                    "description": f"{event_data['title']} brings together researchers and practitioners in Arabic NLP.",
                    "event_type": event_data["type"],
                    "domains": "nlp,arabic_lang,ai",
                    "location": random.choice(
                        [
                            "Virtual",
                            "Dubai, UAE",
                            "Cairo, Egypt",
                            "Riyadh, Saudi Arabia",
                            "Algiers, Algeria",
                        ]
                    ),
                    "start_date": start_date,
                    "end_date": start_date + timedelta(days=random.randint(1, 3)),
                    "submission_deadline": start_date - timedelta(days=30),
                    "organizer": random.choice(institutions),
                    "contact_email": "events@nlp-platform.com",
                    "created_by": admin_user,
                    "is_approved": True,
                    "approval_status": "approved",
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"    Created {created_count} events"))

    def _populate_forum_topics(self, admin_user):
        """Populate forum topics"""
        from forum.models import Topic

        self.stdout.write("  Populating forum topics...")

        topics_data = [
            {
                "title": "Best practices for Arabic tokenization",
                "title_ar": "أفضل الممارسات لتقسيم النص العربي",
            },
            {
                "title": "How to handle Arabic diacritics in NLP?",
                "title_ar": "كيفية التعامل مع التشكيل في معالجة اللغة؟",
            },
            {
                "title": "Recommended Arabic corpora for beginners",
                "title_ar": "المدونات العربية الموصى بها للمبتدئين",
            },
            {
                "title": "AraBERT vs ArabicBERT: Which one to use?",
                "title_ar": "آرابيرت مقابل بيرت العربي: أيهما أفضل؟",
            },
            {
                "title": "Challenges in Arabic speech recognition",
                "title_ar": "تحديات التعرف على الكلام العربي",
            },
            {
                "title": "Building Arabic chatbots: Tips and tricks",
                "title_ar": "بناء روبوتات المحادثة العربية: نصائح وحيل",
            },
            {
                "title": "Arabic sentiment analysis resources",
                "title_ar": "موارد تحليل المشاعر العربية",
            },
            {
                "title": "How to preprocess Arabic text?",
                "title_ar": "كيفية المعالجة المسبقة للنص العربي؟",
            },
            {
                "title": "Open source Arabic NLP tools",
                "title_ar": "أدوات معالجة اللغة العربية مفتوحة المصدر",
            },
            {
                "title": "Dialectal Arabic vs MSA in NLP",
                "title_ar": "اللهجات العربية مقابل الفصحى في المعالجة",
            },
        ]

        created_count = 0
        for topic_data in topics_data:
            topic, created = Topic.objects.get_or_create(
                title=topic_data["title"],
                defaults={
                    "description": f"Discussion about: {topic_data['title']}. Share your experiences and insights!",
                    "creator": admin_user,
                    "approval_status": "approved",
                },
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"    Created {created_count} forum topics")
        )

    def _populate_posts(self, admin_user):
        """Populate QA posts"""
        from QA.models import Post

        self.stdout.write("  Populating posts...")

        posts_data = [
            "I started learning Arabic NLP 6 months ago and here is what I learned. The journey was challenging but rewarding. I highly recommend starting with CAMeL Tools and AraBERT.",
            "Excited to share that we have released a new Arabic sentiment dataset with 50k samples. Check out our GitHub repository for more details!",
            "Here are my top 10 tips for preprocessing Arabic text before feeding it to your models. First, always normalize the text...",
            "I compared AraVec, FastText Arabic, and Arabic-BERT embeddings on multiple tasks. Here are my findings...",
            "I compiled a list of the best Arabic NLP resources available online. Bookmarking this for future reference!",
            "CAMeL Tools has been a game changer for my Arabic NLP projects. Here is why I recommend it to everyone starting in this field.",
            "Sharing my experience dealing with Arabic OCR and the challenges I faced. The biggest issue was with diacritics...",
            "Step-by-step guide on how I built an Arabic spell checker from scratch. The key was to use a good corpus as the base.",
            "I have a corpus with mixed MSA and dialectal Arabic. What is the best way to tokenize it? Any suggestions?",
            "What is the current state-of-the-art model for Arabic Named Entity Recognition? Looking for recommendations.",
            "Should I normalize Hamza and Alef before training or after? This has been confusing me for a while.",
            "What accuracy should I expect for Arabic text classification on news articles? My model is getting 87%.",
            "Is it worth training AraBERT from scratch on domain-specific data? Has anyone tried this before?",
        ]

        created_count = 0
        # Check how many posts already exist to determine if we should add more
        existing_count = Post.objects.filter(author=admin_user).count()

        for content in posts_data:
            if existing_count + created_count >= len(posts_data):
                break
            post = Post.objects.create(
                content=content,
                author=admin_user,
            )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f"    Created {created_count} posts"))
