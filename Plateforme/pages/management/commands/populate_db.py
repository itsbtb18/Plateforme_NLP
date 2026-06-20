from __future__ import annotations

from datetime import date, timedelta
from itertools import cycle, product

from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from events.models import Event
from feed.models import Comment, Post
from forum.models import ChatRoom, Message, Topic
from institutions.models import Country, Institution, Specialty
from pages.models import NewsPublication, Opportunity
from projects.models import Project, ProjectMember
from resources.models import Article, Corpus, Course, Document, FieldChoices, NLPTool
from taxonomy.models import Dataset, NLPMethod, ResearchDomain

User = get_user_model()


COUNTRY_SEEDS = [
    {"code": "DZ", "name_en": "Algeria", "name_ar": "الجزائر"},
    {"code": "SA", "name_en": "Saudi Arabia", "name_ar": "المملكة العربية السعودية"},
    {"code": "EG", "name_en": "Egypt", "name_ar": "مصر"},
    {
        "code": "AE",
        "name_en": "United Arab Emirates",
        "name_ar": "الإمارات العربية المتحدة",
    },
    {"code": "MA", "name_en": "Morocco", "name_ar": "المغرب"},
    {"code": "TN", "name_en": "Tunisia", "name_ar": "تونس"},
    {"code": "JO", "name_en": "Jordan", "name_ar": "الأردن"},
    {"code": "QA", "name_en": "Qatar", "name_ar": "قطر"},
    {"code": "LB", "name_en": "Lebanon", "name_ar": "لبنان"},
    {"code": "IQ", "name_en": "Iraq", "name_ar": "العراق"},
    {"code": "KW", "name_en": "Kuwait", "name_ar": "الكويت"},
    {"code": "OM", "name_en": "Oman", "name_ar": "عُمان"},
    {"code": "BH", "name_en": "Bahrain", "name_ar": "البحرين"},
    {"code": "PS", "name_en": "Palestine", "name_ar": "فلسطين"},
]

SPECIALTY_SEEDS = [
    {"code": "arabic_nlp", "name_en": "Arabic NLP", "name_ar": "معالجة اللغة العربية"},
    {
        "code": "comp_linguistics",
        "name_en": "Computational Linguistics",
        "name_ar": "اللسانيات الحاسوبية",
    },
    {
        "code": "machine_translation",
        "name_en": "Machine Translation",
        "name_ar": "الترجمة الآلية",
    },
    {
        "code": "sentiment_analysis",
        "name_en": "Sentiment Analysis",
        "name_ar": "تحليل المشاعر",
    },
    {
        "code": "named_entity_rec",
        "name_en": "Named Entity Recognition",
        "name_ar": "التعرف على الكيانات المسماة",
    },
    {
        "code": "speech_processing",
        "name_en": "Speech Processing",
        "name_ar": "معالجة الكلام",
    },
    {
        "code": "info_retrieval",
        "name_en": "Information Retrieval",
        "name_ar": "استرجاع المعلومات",
    },
    {
        "code": "corpus_linguistics",
        "name_en": "Corpus Linguistics",
        "name_ar": "لسانيات المدونات",
    },
    {
        "code": "comp_linguistics",
        "name_en": "Computational Linguistics",
        "name_ar": "اللسانيات الحاسوبية",
    },
    {
        "code": "dialect_ident",
        "name_en": "Dialect Identification",
        "name_ar": "تحديد اللهجات",
    },
    {
        "code": "text_summarization",
        "name_en": "Text Summarization",
        "name_ar": "تلخيص النصوص",
    },
    {
        "code": "digital_humanities",
        "name_en": "Digital Humanities",
        "name_ar": "الإنسانيات الرقمية",
    },
    {
        "code": "machine_learning",
        "name_en": "Machine Learning",
        "name_ar": "تعلم الآلة",
    },
    {"code": "morphology", "name_en": "Morphology", "name_ar": "الصرف"},
]

DOMAIN_SEEDS = [
    {
        "name_en": "Arabic NLP",
        "name_ar": "معالجة اللغة العربية",
        "slug": "arabic-nlp",
        "parent": None,
        "description_en": "Core research on Arabic language technologies.",
        "description_ar": "البحث الأساسي في تقنيات اللغة العربية.",
    },
    {
        "name_en": "Morphological Analysis",
        "name_ar": "التحليل الصرفي",
        "slug": "morphological-analysis",
        "parent": "arabic-nlp",
        "description_en": "Root patterns, clitics, and morphological disambiguation.",
        "description_ar": "الجذور واللواصق وإزالة الغموض الصرفي.",
    },
    {
        "name_en": "Dialect Identification",
        "name_ar": "تحديد اللهجات",
        "slug": "dialect-identification",
        "parent": "arabic-nlp",
        "description_en": "Modeling dialectal variation across Arabic speech and text.",
        "description_ar": "نمذجة التنوع اللهجي في النصوص والكلام العربي.",
    },
    {
        "name_en": "Sentiment Analysis",
        "name_ar": "تحليل المشاعر",
        "slug": "sentiment-analysis",
        "parent": "arabic-nlp",
        "description_en": "Opinion mining on Arabic social, news, and review data.",
        "description_ar": "استخراج الرأي والمشاعر من النصوص العربية.",
    },
    {
        "name_en": "Named Entity Recognition",
        "name_ar": "التعرف على الكيانات",
        "slug": "named-entity-recognition",
        "parent": "arabic-nlp",
        "description_en": "People, locations, organizations, and domain entities.",
        "description_ar": "الأشخاص والأماكن والمنظمات والكيانات المتخصصة.",
    },
    {
        "name_en": "Machine Translation",
        "name_ar": "الترجمة الآلية",
        "slug": "machine-translation",
        "parent": "arabic-nlp",
        "description_en": "Arabic-to-English and dialect-to-MSA translation.",
        "description_ar": "الترجمة من العربية إلى الإنجليزية ومن اللهجات إلى العربية الفصحى.",
    },
    {
        "name_en": "Text Summarization",
        "name_ar": "تلخيص النصوص",
        "slug": "text-summarization",
        "parent": "arabic-nlp",
        "description_en": "Extractive and abstractive summarization for Arabic content.",
        "description_ar": "التلخيص الاستخلاصي والتوليدي للنصوص العربية.",
    },
    {
        "name_en": "Information Retrieval",
        "name_ar": "استرجاع المعلومات",
        "slug": "information-retrieval",
        "parent": "arabic-nlp",
        "description_en": "Search, ranking, and retrieval for Arabic collections.",
        "description_ar": "البحث والترتيب واسترجاع المعلومات في المجموعات العربية.",
    },
    {
        "name_en": "Speech Processing",
        "name_ar": "معالجة الكلام",
        "slug": "speech-processing",
        "parent": "arabic-nlp",
        "description_en": "ASR, TTS, and spoken Arabic language technology.",
        "description_ar": "التعرف الآلي على الكلام والنطق الاصطناعي وتقنيات العربية المنطوقة.",
    },
    {
        "name_en": "Corpus Linguistics",
        "name_ar": "لسانيات المدونات",
        "slug": "corpus-linguistics",
        "parent": "arabic-nlp",
        "description_en": "Corpus design, annotation, and quality assurance.",
        "description_ar": "تصميم المدونات اللغوية وتوسيمها وضمان جودتها.",
    },
    {
        "name_en": "Text Mining",
        "name_ar": "تنقيب النصوص",
        "slug": "text-mining",
        "parent": "arabic-nlp",
        "description_en": "Mining patterns from Arabic texts and collections.",
        "description_ar": "استخراج الأنماط من النصوص والمجموعات العربية.",
    },
]

METHOD_SEEDS = [
    {
        "name_en": "Transformer Fine-tuning",
        "name_ar": "الضبط الدقيق للمحولات",
        "slug": "transformer-finetuning",
    },
    {
        "name_en": "Sequence Labeling",
        "name_ar": "وسم التسلسل",
        "slug": "sequence-labeling",
    },
    {
        "name_en": "Multi-task Learning",
        "name_ar": "التعلم متعدد المهام",
        "slug": "multi-task-learning",
    },
    {
        "name_en": "CRF Hybrid Modeling",
        "name_ar": "النمذجة الهجينة مع CRF",
        "slug": "crf-hybrid-modeling",
    },
    {
        "name_en": "Lexicon-assisted Learning",
        "name_ar": "التعلم المدعوم بالمعاجم",
        "slug": "lexicon-assisted-learning",
    },
    {
        "name_en": "Prompt-based Learning",
        "name_ar": "التعلم المعتمد على التلقين",
        "slug": "prompt-based-learning",
    },
    {
        "name_en": "Knowledge Distillation",
        "name_ar": "التقطير المعرفي",
        "slug": "knowledge-distillation",
    },
    {
        "name_en": "Rule-based Preprocessing",
        "name_ar": "المعالجة المسبقة القائمة على القواعد",
        "slug": "rule-based-preprocessing",
    },
    {
        "name_en": "Active Learning",
        "name_ar": "التعلم النشط",
        "slug": "active-learning",
    },
    {
        "name_en": "Contrastive Learning",
        "name_ar": "التعلم التبايني",
        "slug": "contrastive-learning",
    },
]

INSTITUTION_SEEDS = [
    {
        "name_en": "University of Science and Technology Houari Boumediene",
        "name_ar": "جامعة هواري بومدين للعلوم والتكنولوجيا",
        "acronym": "USTHB",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Algiers",
        "city_ar": "الجزائر",
        "website": "https://www.usthb.dz",
        "specialties": ["arabic_nlp", "comp_linguistics", "machine_translation"],
    },
    {
        "name_en": "National School of Computer Science",
        "name_ar": "المدرسة الوطنية العليا للإعلام الآلي",
        "acronym": "ESI",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Algiers",
        "city_ar": "الجزائر",
        "website": "https://www.esi.dz",
        "specialties": ["arabic_nlp", "info_retrieval", "digital_humanities"],
    },
    {
        "name_en": "CERIST Research Center",
        "name_ar": "مركز البحث في الإعلام العلمي والتقني",
        "acronym": "CERIST",
        "type": "Research Center",
        "country_code": "DZ",
        "city_en": "Algiers",
        "city_ar": "الجزائر",
        "website": "https://www.cerist.dz",
        "specialties": ["arabic_nlp", "corpus_linguistics", "info_retrieval"],
    },
    {
        "name_en": "Center for the Development of Advanced Technologies",
        "name_ar": "مركز تطوير التكنولوجيات المتقدمة",
        "acronym": "CDTA",
        "type": "Research Center",
        "country_code": "DZ",
        "city_en": "Algiers",
        "city_ar": "الجزائر",
        "website": "https://www.cdta.dz",
        "specialties": ["speech_processing", "machine_translation", "arabic_nlp"],
    },
    {
        "name_en": "University of Algiers 1",
        "name_ar": "جامعة الجزائر 1",
        "acronym": "UA1",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Algiers",
        "city_ar": "الجزائر",
        "website": "https://www.univ-alger.dz",
        "specialties": ["arabic_nlp", "named_entity_rec", "sentiment_analysis"],
    },
    {
        "name_en": "University of Oran 1 Ahmed Ben Bella",
        "name_ar": "جامعة وهران 1 أحمد بن بلة",
        "acronym": "UO1",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Oran",
        "city_ar": "وهران",
        "website": "https://www.univ-oran1.dz",
        "specialties": ["arabic_nlp", "speech_processing", "info_retrieval"],
    },
    {
        "name_en": "University of Constantine 1",
        "name_ar": "جامعة قسنطينة 1",
        "acronym": "UC1",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Constantine",
        "city_ar": "قسنطينة",
        "website": "https://www.univ-constantine1.dz",
        "specialties": ["arabic_nlp", "comp_linguistics", "text_summarization"],
    },
    {
        "name_en": "University of Bejaia",
        "name_ar": "جامعة بجاية",
        "acronym": "UAMB",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Bejaia",
        "city_ar": "بجاية",
        "website": "https://www.univ-bejaia.dz",
        "specialties": ["sentiment_analysis", "arabic_nlp", "digital_humanities"],
    },
    {
        "name_en": "University of Tlemcen",
        "name_ar": "جامعة تلمسان",
        "acronym": "UTLM",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Tlemcen",
        "city_ar": "تلمسان",
        "website": "https://www.univ-tlemcen.dz",
        "specialties": ["arabic_nlp", "machine_translation", "corpus_linguistics"],
    },
    {
        "name_en": "ENSIA",
        "name_ar": "المدرسة الوطنية العليا للذكاء الاصطناعي",
        "acronym": "ENSIA",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Sidi Abdellah",
        "city_ar": "المدينة الجديدة سيدي عبد الله",
        "website": "https://www.ensia.edu.dz",
        "specialties": ["arabic_nlp", "machine_learning", "comp_linguistics"],
    },
    {
        "name_en": "University of Batna 1",
        "name_ar": "جامعة باتنة 1",
        "acronym": "UB1",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Batna",
        "city_ar": "باتنة",
        "website": "https://www.univ-batna.dz",
        "specialties": ["arabic_nlp", "named_entity_rec", "info_retrieval"],
    },
    {
        "name_en": "University of Sidi Bel Abbes",
        "name_ar": "جامعة سيدي بلعباس",
        "acronym": "USBA",
        "type": "University",
        "country_code": "DZ",
        "city_en": "Sidi Bel Abbes",
        "city_ar": "سيدي بلعباس",
        "website": "https://www.univ-sba.dz",
        "specialties": ["arabic_nlp", "speech_processing", "morphology"],
    },
    {
        "name_en": "University of Tunis El Manar",
        "name_ar": "جامعة تونس المنار",
        "acronym": "UTM",
        "type": "University",
        "country_code": "TN",
        "city_en": "Tunis",
        "city_ar": "تونس",
        "website": "https://www.utm.rnu.tn",
        "specialties": ["arabic_nlp", "comp_linguistics", "sentiment_analysis"],
    },
    {
        "name_en": "University of Sfax",
        "name_ar": "جامعة صفاقس",
        "acronym": "USF",
        "type": "University",
        "country_code": "TN",
        "city_en": "Sfax",
        "city_ar": "صفاقس",
        "website": "https://www.uss.rnu.tn",
        "specialties": ["arabic_nlp", "info_retrieval", "corpus_linguistics"],
    },
    {
        "name_en": "University of Jordan",
        "name_ar": "الجامعة الأردنية",
        "acronym": "UJ",
        "type": "University",
        "country_code": "JO",
        "city_en": "Amman",
        "city_ar": "عمان",
        "website": "https://www.ju.edu.jo",
        "specialties": ["arabic_nlp", "machine_translation", "named_entity_rec"],
    },
    {
        "name_en": "Jordan University of Science and Technology",
        "name_ar": "جامعة العلوم والتكنولوجيا الأردنية",
        "acronym": "JUST",
        "type": "University",
        "country_code": "JO",
        "city_en": "Irbid",
        "city_ar": "إربد",
        "website": "https://www.just.edu.jo",
        "specialties": ["speech_processing", "arabic_nlp", "comp_linguistics"],
    },
    {
        "name_en": "University of Baghdad",
        "name_ar": "جامعة بغداد",
        "acronym": "UOB",
        "type": "University",
        "country_code": "IQ",
        "city_en": "Baghdad",
        "city_ar": "بغداد",
        "website": "https://www.uobaghdad.edu.iq",
        "specialties": ["arabic_nlp", "text_summarization", "digital_humanities"],
    },
    {
        "name_en": "University of Basrah",
        "name_ar": "جامعة البصرة",
        "acronym": "UBS",
        "type": "University",
        "country_code": "IQ",
        "city_en": "Basrah",
        "city_ar": "البصرة",
        "website": "https://www.uobasrah.edu.iq",
        "specialties": ["arabic_nlp", "info_retrieval", "corpus_linguistics"],
    },
    {
        "name_en": "King Abdulaziz University",
        "name_ar": "جامعة الملك عبدالعزيز",
        "acronym": "KAU",
        "type": "University",
        "country_code": "SA",
        "city_en": "Jeddah",
        "city_ar": "جدة",
        "website": "https://www.kau.edu.sa",
        "specialties": ["arabic_nlp", "machine_translation", "sentiment_analysis"],
    },
    {
        "name_en": "King Saud University",
        "name_ar": "جامعة الملك سعود",
        "acronym": "KSU",
        "type": "University",
        "country_code": "SA",
        "city_en": "Riyadh",
        "city_ar": "الرياض",
        "website": "https://www.ksu.edu.sa",
        "specialties": ["arabic_nlp", "speech_processing", "comp_linguistics"],
    },
    {
        "name_en": "King Abdullah University of Science and Technology",
        "name_ar": "جامعة الملك عبدالله للعلوم والتقنية",
        "acronym": "KAUST",
        "type": "University",
        "country_code": "SA",
        "city_en": "Thuwal",
        "city_ar": "ثول",
        "website": "https://www.kaust.edu.sa",
        "specialties": ["arabic_nlp", "machine_learning", "info_retrieval"],
    },
    {
        "name_en": "Qatar University",
        "name_ar": "جامعة قطر",
        "acronym": "QU",
        "type": "University",
        "country_code": "QA",
        "city_en": "Doha",
        "city_ar": "الدوحة",
        "website": "https://www.qu.edu.qa",
        "specialties": ["arabic_nlp", "speech_processing", "dialect_ident"],
    },
    {
        "name_en": "Hamad Bin Khalifa University",
        "name_ar": "جامعة حمد بن خليفة",
        "acronym": "HBKU",
        "type": "University",
        "country_code": "QA",
        "city_en": "Doha",
        "city_ar": "الدوحة",
        "website": "https://www.hbku.edu.qa",
        "specialties": ["arabic_nlp", "info_retrieval", "digital_humanities"],
    },
    {
        "name_en": "Qatar Computing Research Institute",
        "name_ar": "معهد قطر لبحوث الحوسبة",
        "acronym": "QCRI",
        "type": "Research Center",
        "country_code": "QA",
        "city_en": "Doha",
        "city_ar": "الدوحة",
        "website": "https://www.hbku.edu.qa/qcri",
        "specialties": ["arabic_nlp", "machine_translation", "named_entity_rec"],
    },
    {
        "name_en": "Khalifa University",
        "name_ar": "جامعة خليفة",
        "acronym": "KU",
        "type": "University",
        "country_code": "AE",
        "city_en": "Abu Dhabi",
        "city_ar": "أبوظبي",
        "website": "https://www.ku.ac.ae",
        "specialties": ["arabic_nlp", "speech_processing", "machine_learning"],
    },
    {
        "name_en": "United Arab Emirates University",
        "name_ar": "جامعة الإمارات العربية المتحدة",
        "acronym": "UAEU",
        "type": "University",
        "country_code": "AE",
        "city_en": "Al Ain",
        "city_ar": "العين",
        "website": "https://www.uaeu.ac.ae",
        "specialties": ["arabic_nlp", "dialect_ident", "corpus_linguistics"],
    },
    {
        "name_en": "University of Sharjah",
        "name_ar": "جامعة الشارقة",
        "acronym": "UOS",
        "type": "University",
        "country_code": "AE",
        "city_en": "Sharjah",
        "city_ar": "الشارقة",
        "website": "https://www.sharjah.ac.ae",
        "specialties": ["arabic_nlp", "info_retrieval", "sentiment_analysis"],
    },
    {
        "name_en": "Mohammed V University",
        "name_ar": "جامعة محمد الخامس",
        "acronym": "UM5",
        "type": "University",
        "country_code": "MA",
        "city_en": "Rabat",
        "city_ar": "الرباط",
        "website": "https://www.um5.ac.ma",
        "specialties": ["arabic_nlp", "corpus_linguistics", "named_entity_rec"],
    },
    {
        "name_en": "Hassan II University of Casablanca",
        "name_ar": "جامعة الحسن الثاني بالدار البيضاء",
        "acronym": "UH2",
        "type": "University",
        "country_code": "MA",
        "city_en": "Casablanca",
        "city_ar": "الدار البيضاء",
        "website": "https://www.univh2c.ma",
        "specialties": ["arabic_nlp", "machine_translation", "comp_linguistics"],
    },
    {
        "name_en": "Cadi Ayyad University",
        "name_ar": "جامعة القاضي عياض",
        "acronym": "UCA",
        "type": "University",
        "country_code": "MA",
        "city_en": "Marrakesh",
        "city_ar": "مراكش",
        "website": "https://www.uca.ma",
        "specialties": ["arabic_nlp", "speech_processing", "info_retrieval"],
    },
    {
        "name_en": "Cairo University",
        "name_ar": "جامعة القاهرة",
        "acronym": "CU",
        "type": "University",
        "country_code": "EG",
        "city_en": "Cairo",
        "city_ar": "القاهرة",
        "website": "https://cu.edu.eg",
        "specialties": ["arabic_nlp", "machine_translation", "text_summarization"],
    },
    {
        "name_en": "Ain Shams University",
        "name_ar": "جامعة عين شمس",
        "acronym": "ASU",
        "type": "University",
        "country_code": "EG",
        "city_en": "Cairo",
        "city_ar": "القاهرة",
        "website": "https://www.asu.edu.eg",
        "specialties": ["arabic_nlp", "named_entity_rec", "sentiment_analysis"],
    },
    {
        "name_en": "Alexandria University",
        "name_ar": "جامعة الإسكندرية",
        "acronym": "AU",
        "type": "University",
        "country_code": "EG",
        "city_en": "Alexandria",
        "city_ar": "الإسكندرية",
        "website": "https://www.alexu.edu.eg",
        "specialties": ["arabic_nlp", "info_retrieval", "digital_humanities"],
    },
    {
        "name_en": "American University of Beirut",
        "name_ar": "الجامعة الأميركية في بيروت",
        "acronym": "AUB",
        "type": "University",
        "country_code": "LB",
        "city_en": "Beirut",
        "city_ar": "بيروت",
        "website": "https://www.aub.edu.lb",
        "specialties": ["arabic_nlp", "comp_linguistics", "corpus_linguistics"],
    },
    {
        "name_en": "Lebanese University",
        "name_ar": "الجامعة اللبنانية",
        "acronym": "UL",
        "type": "University",
        "country_code": "LB",
        "city_en": "Beirut",
        "city_ar": "بيروت",
        "website": "https://www.ul.edu.lb",
        "specialties": ["arabic_nlp", "speech_processing", "dialect_ident"],
    },
    {
        "name_en": "Sultan Qaboos University",
        "name_ar": "جامعة السلطان قابوس",
        "acronym": "SQU",
        "type": "University",
        "country_code": "OM",
        "city_en": "Muscat",
        "city_ar": "مسقط",
        "website": "https://www.squ.edu.om",
        "specialties": ["arabic_nlp", "machine_translation", "info_retrieval"],
    },
    {
        "name_en": "Kuwait University",
        "name_ar": "جامعة الكويت",
        "acronym": "KUW",
        "type": "University",
        "country_code": "KW",
        "city_en": "Kuwait City",
        "city_ar": "مدينة الكويت",
        "website": "https://www.ku.edu.kw",
        "specialties": ["arabic_nlp", "sentiment_analysis", "text_summarization"],
    },
    {
        "name_en": "University of Bahrain",
        "name_ar": "جامعة البحرين",
        "acronym": "UOBH",
        "type": "University",
        "country_code": "BH",
        "city_en": "Sakhir",
        "city_ar": "الصخير",
        "website": "https://www.uob.edu.bh",
        "specialties": ["arabic_nlp", "named_entity_rec", "corpus_linguistics"],
    },
    {
        "name_en": "An-Najah National University",
        "name_ar": "جامعة النجاح الوطنية",
        "acronym": "ANNU",
        "type": "University",
        "country_code": "PS",
        "city_en": "Nablus",
        "city_ar": "نابلس",
        "website": "https://www.najah.edu",
        "specialties": ["arabic_nlp", "machine_translation", "info_retrieval"],
    },
]

RESEARCHER_SEEDS = [
    {
        "name_en": "Nizar Habash",
        "name_ar": "نزار حبش",
        "institution_code": "KAU",
        "specialty_code": "comp_linguistics",
    },
    {
        "name_en": "Mona Diab",
        "name_ar": "منى دياب",
        "institution_code": "QCRI",
        "specialty_code": "sentiment_analysis",
    },
    {
        "name_en": "Houda Bouamor",
        "name_ar": "هدى بوعمور",
        "institution_code": "QCRI",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Hamdy Mubarak",
        "name_ar": "حمدي مبارك",
        "institution_code": "QCRI",
        "specialty_code": "machine_translation",
    },
    {
        "name_en": "Samhaa R. El-Beltagy",
        "name_ar": "سمحة ر. البلتاجي",
        "institution_code": "CU",
        "specialty_code": "sentiment_analysis",
    },
    {
        "name_en": "Wajdi Zaghouani",
        "name_ar": "وجدي الزغواني",
        "institution_code": "HBKU",
        "specialty_code": "corpus_linguistics",
    },
    {
        "name_en": "Fatiha Sadat",
        "name_ar": "فتيحة سعدات",
        "institution_code": "UM5",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Kareem Darwish",
        "name_ar": "كريم درويش",
        "institution_code": "QCRI",
        "specialty_code": "info_retrieval",
    },
    {
        "name_en": "Mohamed Attia",
        "name_ar": "محمد عطية",
        "institution_code": "KAU",
        "specialty_code": "machine_translation",
    },
    {
        "name_en": "AbdelRahim Elmadany",
        "name_ar": "عبد الرحيم المعدني",
        "institution_code": "QCRI",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Muhammad Abdul-Mageed",
        "name_ar": "محمد عبد المجيد",
        "institution_code": "KAUST",
        "specialty_code": "comp_linguistics",
    },
    {
        "name_en": "Abeer Alhindi",
        "name_ar": "عبير الهندي",
        "institution_code": "KAU",
        "specialty_code": "named_entity_rec",
    },
    {
        "name_en": "Hany Hassan",
        "name_ar": "هاني حسن",
        "institution_code": "QCRI",
        "specialty_code": "speech_processing",
    },
    {
        "name_en": "Tamer Elsayed",
        "name_ar": "تامر السيد",
        "institution_code": "QCRI",
        "specialty_code": "info_retrieval",
    },
    {
        "name_en": "Ibrahim Alsmari",
        "name_ar": "إبراهيم السميري",
        "institution_code": "KSU",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Ayman Mourad",
        "name_ar": "أيمن مراد",
        "institution_code": "USTHB",
        "specialty_code": "machine_translation",
    },
    {
        "name_en": "Sherif Mahdy",
        "name_ar": "شريف مهدي",
        "institution_code": "ASU",
        "specialty_code": "named_entity_rec",
    },
    {
        "name_en": "Sara Alotaibi",
        "name_ar": "سارة العتيبي",
        "institution_code": "KSU",
        "specialty_code": "sentiment_analysis",
    },
    {
        "name_en": "Huda Alsmail",
        "name_ar": "هدى الإسماعيل",
        "institution_code": "KU",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Rania Abdelzaher",
        "name_ar": "رانيا عبد الظاهر",
        "institution_code": "AUB",
        "specialty_code": "digital_humanities",
    },
    {
        "name_en": "Dyaa Albakour",
        "name_ar": "ضياء البكور",
        "institution_code": "UJ",
        "specialty_code": "info_retrieval",
    },
    {
        "name_en": "Maha Elkomy",
        "name_ar": "مها الكومي",
        "institution_code": "ASU",
        "specialty_code": "sentiment_analysis",
    },
    {
        "name_en": "Reem Faraj",
        "name_ar": "ريم فرج",
        "institution_code": "UAEU",
        "specialty_code": "corpus_linguistics",
    },
    {
        "name_en": "Ahmed El-Sayed",
        "name_ar": "أحمد السيد",
        "institution_code": "USTHB",
        "specialty_code": "machine_learning",
    },
    {
        "name_en": "Yasser El Bassiouny",
        "name_ar": "ياسر البسيوني",
        "institution_code": "CU",
        "specialty_code": "machine_translation",
    },
    {
        "name_en": "Doaa Moawad",
        "name_ar": "دعاء معوض",
        "institution_code": "ALEX",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Amr Elsayed",
        "name_ar": "عمرو السيد",
        "institution_code": "ESI",
        "specialty_code": "info_retrieval",
    },
    {
        "name_en": "Hossam Darwish",
        "name_ar": "حسام درويش",
        "institution_code": "CERIST",
        "specialty_code": "corpus_linguistics",
    },
    {
        "name_en": "Noura Al Nuaimi",
        "name_ar": "نورة النعيمي",
        "institution_code": "HBKU",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Khaled Shaalan",
        "name_ar": "خالد شعلان",
        "institution_code": "KSU",
        "specialty_code": "comp_linguistics",
    },
    {
        "name_en": "Oday Obeidat",
        "name_ar": "عدي عبيدات",
        "institution_code": "JUST",
        "specialty_code": "speech_processing",
    },
    {
        "name_en": "Abdulrahman Alharbi",
        "name_ar": "عبد الرحمن الحربي",
        "institution_code": "KAU",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Saud Alotaibi",
        "name_ar": "سعود العتيبي",
        "institution_code": "KSU",
        "specialty_code": "machine_translation",
    },
    {
        "name_en": "Mohammed Alghamdi",
        "name_ar": "محمد الغامدي",
        "institution_code": "KAU",
        "specialty_code": "speech_processing",
    },
    {
        "name_en": "Fatimah Alshammari",
        "name_ar": "فاطمة الشمري",
        "institution_code": "KSU",
        "specialty_code": "sentiment_analysis",
    },
    {
        "name_en": "Hisham Al-Maadeed",
        "name_ar": "هشام المعاضيد",
        "institution_code": "HBKU",
        "specialty_code": "info_retrieval",
    },
    {
        "name_en": "Ali Al-Sherif",
        "name_ar": "علي الشريف",
        "institution_code": "AUB",
        "specialty_code": "digital_humanities",
    },
    {
        "name_en": "Lina El-Masry",
        "name_ar": "لينا المصري",
        "institution_code": "UAEU",
        "specialty_code": "named_entity_rec",
    },
    {
        "name_en": "Rana Alhammadi",
        "name_ar": "رنا الحمادي",
        "institution_code": "KU",
        "specialty_code": "arabic_nlp",
    },
    {
        "name_en": "Abdelkader Lamouchi",
        "name_ar": "عبد القادر لموشي",
        "institution_code": "USTHB",
        "specialty_code": "comp_linguistics",
    },
]

TOOL_BASES = [
    {
        "name": "CAMeL Tools",
        "tool_type": "tokenization",
        "version": "1.5.0",
        "organization": "QCRI",
    },
    {
        "name": "Farasa",
        "tool_type": "stemming",
        "version": "0.9",
        "organization": "QCRI",
    },
    {
        "name": "Stanza Arabic",
        "tool_type": "ner",
        "version": "1.8.2",
        "organization": "Stanford NLP Group",
    },
    {
        "name": "AraBERT",
        "tool_type": "sentiment_analysis",
        "version": "2.0",
        "organization": "QCRI",
    },
    {
        "name": "AraBART",
        "tool_type": "machine_translation",
        "version": "1.0",
        "organization": "QCRI",
    },
    {
        "name": "AraGPT2",
        "tool_type": "pos_tagging",
        "version": "1.0",
        "organization": "QCRI",
    },
    {
        "name": "MARBERT",
        "tool_type": "sentiment_analysis",
        "version": "1.0",
        "organization": "QCRI",
    },
    {"name": "ARBERT", "tool_type": "ner", "version": "1.0", "organization": "QCRI"},
    {
        "name": "MADAMIRA",
        "tool_type": "pos_tagging",
        "version": "2.1",
        "organization": "Columbia University / QCRI",
    },
    {
        "name": "Qalsadi",
        "tool_type": "stemming",
        "version": "0.5",
        "organization": "Open Source Community",
    },
]

TOOL_VARIANTS = [
    {
        "suffix": "Morphology Pipeline",
        "supported_languages": "ar",
        "use_case": "morphology",
    },
    {"suffix": "Dialect ID Suite", "supported_languages": "ar", "use_case": "dialect"},
    {
        "suffix": "Annotation Toolkit",
        "supported_languages": "ar",
        "use_case": "annotation",
    },
    {
        "suffix": "Benchmark Pack",
        "supported_languages": "ar",
        "use_case": "benchmarking",
    },
]

DATASET_BASES = [
    {
        "name": "PADT",
        "description_en": "Penn Arabic Dependency Treebank benchmark.",
        "description_ar": "مدونة معيارية عربية للاعتماديات الصرفية والنحوية.",
    },
    {
        "name": "ANERcorp",
        "description_en": "Arabic named entity recognition corpus.",
        "description_ar": "مدونة عربية للتعرف على الكيانات المسماة.",
    },
    {
        "name": "ASTD",
        "description_en": "Arabic sentiment tweets dataset.",
        "description_ar": "مجموعة بيانات عربية لتحليل المشاعر في التغريدات.",
    },
    {
        "name": "ArSAS",
        "description_en": "Arabic speech act and sentiment data.",
        "description_ar": "مجموعة عربية للتوجيهات الخطابية وتحليل المشاعر.",
    },
    {
        "name": "LABR",
        "description_en": "Large-scale Arabic book reviews dataset.",
        "description_ar": "مراجعات كتب عربية واسعة النطاق.",
    },
    {
        "name": "DART",
        "description_en": "Arabic dialogue and response tracking dataset.",
        "description_ar": "مجموعة عربية للحوار وتتبع الاستجابة.",
    },
    {
        "name": "MADAR",
        "description_en": "Multidialect Arabic parallel resource.",
        "description_ar": "موارد عربية متوازية متعددة اللهجات.",
    },
    {
        "name": "AQMAR",
        "description_en": "Arabic question answering benchmark.",
        "description_ar": "مرجع معياري عربي للأسئلة والأجوبة.",
    },
    {
        "name": "OSIAN",
        "description_en": "Arabic social media corpus for political discourse.",
        "description_ar": "مدونة عربية لوسائل التواصل في الخطاب العام.",
    },
    {
        "name": "Tashkeela",
        "description_en": "Large Arabic diacritized text collection.",
        "description_ar": "مجموعة نصوص عربية مشكولة على نطاق واسع.",
    },
]

DATASET_VARIANTS = [
    {"suffix": "Tokenization Benchmark"},
    {"suffix": "Dialect Benchmark"},
    {"suffix": "Sentiment Benchmark"},
    {"suffix": "NER Benchmark"},
]

CORPUS_BASES = [
    {
        "name": "Arabic Gigaword",
        "description_en": "Large-scale Arabic newswire corpus.",
        "description_ar": "مدونة أخبار عربية واسعة النطاق.",
    },
    {
        "name": "OpenITI",
        "description_en": "Open Arabic historical texts corpus.",
        "description_ar": "مدونة مفتوحة للنصوص العربية التاريخية.",
    },
    {
        "name": "Arabic Wikipedia",
        "description_en": "Wikipedia content in Modern Standard Arabic.",
        "description_ar": "محتوى ويكيبيديا باللغة العربية الفصحى.",
    },
    {
        "name": "Quranic Arabic Corpus",
        "description_en": "Annotated Quranic Arabic corpus.",
        "description_ar": "مدونة عربية مشروحة للقرآن الكريم.",
    },
    {
        "name": "Aljazeera News Corpus",
        "description_en": "Arabic news collection from Aljazeera-style journalism.",
        "description_ar": "مدونة أخبار عربية مستمدة من الصحافة الإخبارية.",
    },
    {
        "name": "QALB Corpus",
        "description_en": "Arabic proofreading and correction corpus.",
        "description_ar": "مدونة عربية للتدقيق اللغوي والإصلاح الآلي.",
    },
    {
        "name": "ArCOV-19 Corpus",
        "description_en": "Arabic COVID-19 social media corpus.",
        "description_ar": "مدونة عربية خاصة بجائحة كوفيد-19 على وسائل التواصل.",
    },
    {
        "name": "MSA Treebank",
        "description_en": "Modern Standard Arabic treebank.",
        "description_ar": "مدونة إعرابية للعربية الفصحى الحديثة.",
    },
    {
        "name": "CATiB Treebank",
        "description_en": "Arabic syntactic treebank for dependency parsing.",
        "description_ar": "مدونة عربية نحوية لتحليل الاعتماديات.",
    },
    {
        "name": "KSUCCA",
        "description_en": "King Saud University Corpus of Classical Arabic.",
        "description_ar": "مدونة جامعة الملك سعود للعربية الكلاسيكية.",
    },
]

CORPUS_VARIANTS = [
    {"suffix": "News Collection"},
    {"suffix": "Social Media Collection"},
    {"suffix": "Scholarly Collection"},
    {"suffix": "Dialect Collection"},
]

COURSE_THEMES = [
    {
        "title": "Arabic NLP with Transformers",
        "field": FieldChoices.NLP,
        "level": "master",
    },
    {
        "title": "Computational Morphology for Arabic",
        "field": FieldChoices.LINGUISTICS,
        "level": "master",
    },
    {
        "title": "Dialectal Arabic Processing",
        "field": FieldChoices.ARABIC_LINGUISTICS,
        "level": "bachelor",
    },
    {
        "title": "Arabic Sentiment Analysis",
        "field": FieldChoices.SENTIMENT_ANALYSIS,
        "level": "master",
    },
    {
        "title": "Arabic NER for Scientific Text",
        "field": FieldChoices.NAMED_ENTITY,
        "level": "master",
    },
    {
        "title": "Machine Translation for Arabic Dialects",
        "field": FieldChoices.TRANSLATION,
        "level": "doctorate",
    },
    {
        "title": "Diacritization and Normalization",
        "field": FieldChoices.MORPHOLOGY,
        "level": "bachelor",
    },
    {
        "title": "Arabic Information Retrieval",
        "field": FieldChoices.INFORMATION_RETRIEVAL,
        "level": "master",
    },
    {
        "title": "Speech Technology for Arabic",
        "field": FieldChoices.SPEECH_PROCESSING,
        "level": "master",
    },
    {
        "title": "Evaluating Arabic LLMs",
        "field": FieldChoices.ARTIFICIAL_INTELLIGENCE,
        "level": "doctorate",
    },
]

PROJECT_THEMES = [
    {
        "title": "Arabic Dialect Identification",
        "domain_slugs": ["dialect-identification", "arabic-nlp"],
        "method_slugs": ["transformer-finetuning", "contrastive-learning"],
        "dataset_names": ["MADAR", "OSIAN"],
    },
    {
        "title": "Low-Resource Arabic Machine Translation",
        "domain_slugs": ["machine-translation", "arabic-nlp"],
        "method_slugs": ["sequence-labeling", "knowledge-distillation"],
        "dataset_names": ["MADAR", "DART"],
    },
    {
        "title": "Scientific Arabic NER",
        "domain_slugs": ["named-entity-recognition", "arabic-nlp"],
        "method_slugs": ["sequence-labeling", "crf-hybrid-modeling"],
        "dataset_names": ["ANERcorp", "PADT"],
    },
    {
        "title": "Arabic QA for Scholarly Resources",
        "domain_slugs": ["information-retrieval", "arabic-nlp"],
        "method_slugs": ["prompt-based-learning", "active-learning"],
        "dataset_names": ["AQMAR", "Arabic Gigaword"],
    },
    {
        "title": "Arabic News Summarization Benchmark",
        "domain_slugs": ["text-summarization", "corpus-linguistics"],
        "method_slugs": ["transformer-finetuning", "contrastive-learning"],
        "dataset_names": ["Arabic Gigaword", "Aljazeera News Corpus"],
    },
    {
        "title": "Arabic Diacritization Suite",
        "domain_slugs": ["morphological-analysis", "arabic-nlp"],
        "method_slugs": ["rule-based-preprocessing", "knowledge-distillation"],
        "dataset_names": ["Tashkeela", "Quranic Arabic Corpus"],
    },
    {
        "title": "Historical Arabic OCR and Normalization",
        "domain_slugs": ["digital-humanities", "corpus-linguistics"],
        "method_slugs": ["contrastive-learning", "rule-based-preprocessing"],
        "dataset_names": ["OpenITI", "Arabic Wikipedia"],
    },
    {
        "title": "Maghrebi Sentiment Analytics",
        "domain_slugs": ["sentiment-analysis", "dialect-identification"],
        "method_slugs": ["transformer-finetuning", "lexicon-assisted-learning"],
        "dataset_names": ["ArSAS", "ASTD"],
    },
    {
        "title": "Arabic LLM Evaluation Framework",
        "domain_slugs": ["arabic-nlp", "information-retrieval"],
        "method_slugs": ["prompt-based-learning", "multi-task-learning"],
        "dataset_names": ["LABR", "OSACT"],
    },
    {
        "title": "Corpus Cleaning for Arabic News",
        "domain_slugs": ["corpus-linguistics", "text-mining"],
        "method_slugs": ["active-learning", "rule-based-preprocessing"],
        "dataset_names": ["Arabic Gigaword", "ArCOV-19 Corpus"],
    },
]

EVENT_THEMES = [
    {
        "title": "WANLP 2025 Doctoral Consortium",
        "event_type": "conference",
        "language": "en",
    },
    {
        "title": "ArabicNLP 2025 Shared Tasks",
        "event_type": "workshop",
        "language": "en",
    },
    {"title": "ACL Arabic Workshop 2025", "event_type": "workshop", "language": "en"},
    {
        "title": "EMNLP Arabic NLP Tutorial 2025",
        "event_type": "seminar",
        "language": "en",
    },
    {
        "title": "COLING Arabic Corpus Day 2025",
        "event_type": "conference",
        "language": "en",
    },
    {
        "title": "LREC-COLING Arabic Benchmark Track 2026",
        "event_type": "call_for_papers",
        "language": "en",
    },
    {
        "title": "SemEval Arabic Shared Task Meetup 2025",
        "event_type": "seminar",
        "language": "en",
    },
    {
        "title": "EACL Arabic Doctoral Consortium 2026",
        "event_type": "conference",
        "language": "en",
    },
    {
        "title": "RANLP Arabic Speech Workshop 2025",
        "event_type": "workshop",
        "language": "en",
    },
    {
        "title": "NAACL Arabic Evaluation Clinic 2026",
        "event_type": "other",
        "language": "en",
    },
]

OPPORTUNITY_THEMES = [
    {
        "title": "PhD Researcher in Arabic Dialects",
        "opportunity_type": "phd",
        "mode": "onsite",
        "level": "researcher",
    },
    {
        "title": "Research Engineer for Arabic NER",
        "opportunity_type": "job",
        "mode": "hybrid",
        "level": "senior",
    },
    {
        "title": "Machine Translation Intern",
        "opportunity_type": "internship",
        "mode": "hybrid",
        "level": "junior",
    },
    {
        "title": "Corpus Annotation Lead",
        "opportunity_type": "collab",
        "mode": "onsite",
        "level": "researcher",
    },
    {
        "title": "Postdoctoral Fellow in Arabic LLMs",
        "opportunity_type": "phd",
        "mode": "onsite",
        "level": "researcher",
    },
    {
        "title": "NLP Product Researcher",
        "opportunity_type": "job",
        "mode": "remote",
        "level": "senior",
    },
    {
        "title": "Shared Task Coordinator",
        "opportunity_type": "collab",
        "mode": "remote",
        "level": "researcher",
    },
    {
        "title": "Arabic Speech Research Assistant",
        "opportunity_type": "internship",
        "mode": "onsite",
        "level": "student",
    },
    {
        "title": "Open-source Engineer for CAMeL Integration",
        "opportunity_type": "job",
        "mode": "remote",
        "level": "junior",
    },
    {
        "title": "Data Curator for Arabic Benchmarks",
        "opportunity_type": "collab",
        "mode": "hybrid",
        "level": "researcher",
    },
]

NEWS_THEMES = [
    {"title": "Arabic NER Benchmark Release", "type": "paper", "venue": "ACL 2025"},
    {"title": "Dataset Release Announcement", "type": "dataset", "venue": "QCRI"},
    {"title": "Workshop Call for Papers", "type": "event", "venue": "WANLP 2025"},
    {"title": "Shared Task Results", "type": "news", "venue": "ArabicNLP 2025"},
    {"title": "Open-source Toolkit Update", "type": "tool", "venue": "CAMeL Tools"},
    {"title": "Grant Award Announcement", "type": "news", "venue": "USTHB"},
    {"title": "Annual Research Report", "type": "news", "venue": "CERIST"},
    {"title": "Hackathon Winners Announcement", "type": "event", "venue": "ESI"},
    {
        "title": "Special Issue Publication",
        "type": "thesis",
        "venue": "Arabic NLP Journal",
    },
    {"title": "Collaboration Memorandum", "type": "news", "venue": "Qatar University"},
]

FORUM_THEMES = [
    {
        "title": "Best Practices for Arabic Tokenization",
        "description": "Discussion of segmentation rules for clitics, prefixes, and dialectal variants.",
    },
    {
        "title": "Handling Dialectal Normalization",
        "description": "Methods for normalizing Maghrebi and Levantine text before modeling.",
    },
    {
        "title": "Annotation Guidelines for Arabic NER",
        "description": "Clear entity boundaries for people, organizations, locations, and products.",
    },
    {
        "title": "Evaluating Arabic MT Systems",
        "description": "Practical evaluation protocols for Arabic-to-English and dialect translation.",
    },
    {
        "title": "Building Arabic Sentiment Benchmarks",
        "description": "Curation of balanced labels, domain coverage, and annotation quality.",
    },
    {
        "title": "Diacritization in News Text",
        "description": "Trade-offs between accuracy, readability, and throughput in news pipelines.",
    },
    {
        "title": "Corpus Quality Control for Arabic",
        "description": "Deduplication, normalization, and metadata consistency for corpora.",
    },
    {
        "title": "Arabic LLM Prompt Design",
        "description": "Prompt structures that improve reasoning and Arabic generation quality.",
    },
    {
        "title": "Scientific Abstract Summarization",
        "description": "Extractive and abstractive summarization for papers and abstracts.",
    },
    {
        "title": "Low-resource Dataset Collection",
        "description": "Ethical collection and publication of Arabic resources in low-resource settings.",
    },
]

FEED_THEMES = [
    {"title": "Research Lab Update", "category": "announcement"},
    {"title": "Dataset Curation Note", "category": "paper"},
    {"title": "Workshop Recap", "category": "news"},
    {"title": "Paper Announcement", "category": "paper"},
    {"title": "Tool Release Note", "category": "announcement"},
    {"title": "Benchmark Progress Update", "category": "news"},
    {"title": "Collaboration Invitation", "category": "announcement"},
    {"title": "Annotation Sprint Summary", "category": "blog"},
    {"title": "Scholarship Opportunity", "category": "announcement"},
    {"title": "Community Highlight", "category": "news"},
]


def slug_for(text: str) -> str:
    return slugify(text).replace("-", "_")[:90]


class Command(BaseCommand):
    help = "Populate the database with realistic Arabic NLP research data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear generated records before seeding",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        with transaction.atomic():
            self.stdout.write(self.style.NOTICE("Starting Arabic NLP population..."))

            admin = self._get_or_create_admin()

            countries = self._seed_countries()
            specialties = self._seed_specialties()
            domains = self._seed_domains()
            methods = self._seed_methods()
            institutions = self._seed_institutions(countries, specialties, admin, reset)
            users = self._seed_users(institutions, domains, reset)

            course_anchor_institutions = self._pick_institutions(
                institutions, ["USTHB", "ESI", "CERIST", "KAU"]
            )
            project_anchor_institutions = self._pick_institutions(
                institutions, ["USTHB", "ESI", "CERIST", "QCRI"]
            )
            event_anchor_institutions = self._pick_institutions(
                institutions, ["USTHB", "ESI", "CERIST", "KSU"]
            )
            opportunity_anchor_institutions = self._pick_institutions(
                institutions, ["USTHB", "QCRI", "KAU", "HBKU"]
            )
            news_anchor_institutions = self._pick_institutions(
                institutions, ["USTHB", "CERIST", "QCRI", "KAU"]
            )
            forum_anchor_institutions = self._pick_institutions(
                institutions, ["USTHB", "ESI", "CERIST", "QCRI"]
            )
            feed_anchor_institutions = self._pick_institutions(
                institutions, ["USTHB", "ESI", "CERIST", "QCRI"]
            )
            institution_list = list(institutions.values())

            datasets = self._seed_datasets(reset)
            corpora = self._seed_corpora(reset)
            tools = self._seed_tools(admin, reset)
            courses = self._seed_courses(users, course_anchor_institutions, reset)
            documents, articles = self._seed_articles(users, institution_list, reset)
            projects = self._seed_projects(
                users, project_anchor_institutions, domains, methods, datasets, reset
            )
            events = self._seed_events(users, event_anchor_institutions, admin, reset)
            opportunities = self._seed_opportunities(
                users, opportunity_anchor_institutions, admin, reset
            )
            news = self._seed_news(users, news_anchor_institutions, reset)
            posts = self._seed_feed(users, feed_anchor_institutions, reset)
            topics = self._seed_forum(
                users, forum_anchor_institutions, projects, events, posts, reset
            )

            self.stdout.write(self.style.SUCCESS("Population complete."))
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created/updated: {len(users)} users, {len(projects)} projects, {len(courses)} courses, {len(tools)} tools, {len(datasets)} datasets, {len(corpora)} corpora, {len(articles)} articles, {len(institutions)} institutions, {len(events)} events, {len(opportunities)} opportunities, {len(news)} news items, {len(topics)} forum topics, {len(posts)} feed posts."
                )
            )

    def _get_or_create_admin(self):
        admin_email = "admin@sanad.dz"
        admin = User.objects.filter(email=admin_email).first()
        if admin is None:
            admin = User.objects.create_superuser(
                email=admin_email,
                password="SanadAdmin#2026",
                full_name_en="Sanad Platform Administrator",
                full_name_ar="مدير منصة سند",
            )
        admin.is_verified = True
        admin.is_email_verified = True
        admin.status = "active"
        admin.full_name = admin.full_name_en
        admin.save()
        return admin

    def _seed_countries(self):
        countries = {}
        for row in COUNTRY_SEEDS:
            country, created = Country.objects.get_or_create(
                code=row["code"],
                defaults={"name_en": row["name_en"], "name_ar": row["name_ar"]},
            )
            if not created and (
                country.name_en != row["name_en"] or country.name_ar != row["name_ar"]
            ):
                country.name_en = row["name_en"]
                country.name_ar = row["name_ar"]
                country.save(update_fields=["name_en", "name_ar"])
            countries[row["code"]] = country
        return countries

    def _seed_specialties(self):
        specialties = {}
        for row in SPECIALTY_SEEDS:
            specialty, created = Specialty.objects.get_or_create(
                code=row["code"],
                defaults={"name_en": row["name_en"], "name_ar": row["name_ar"]},
            )
            if not created and (
                specialty.name_en != row["name_en"]
                or specialty.name_ar != row["name_ar"]
            ):
                specialty.name_en = row["name_en"]
                specialty.name_ar = row["name_ar"]
                specialty.save(update_fields=["name_en", "name_ar"])
            specialties[row["code"]] = specialty
        return specialties

    def _seed_domains(self):
        domains = {}
        for row in DOMAIN_SEEDS:
            parent = domains.get(row["parent"]) if row["parent"] else None
            domain, created = ResearchDomain.objects.get_or_create(
                slug=row["slug"],
                defaults={
                    "name_en": row["name_en"],
                    "name_ar": row["name_ar"],
                    "parent": parent,
                    "description_en": row["description_en"],
                    "description_ar": row["description_ar"],
                },
            )
            changed = False
            for field_name in [
                "name_en",
                "name_ar",
                "description_en",
                "description_ar",
            ]:
                if getattr(domain, field_name) != row[field_name]:
                    setattr(domain, field_name, row[field_name])
                    changed = True
            if domain.parent != parent:
                domain.parent = parent
                changed = True
            if changed:
                domain.save()
            domains[row["slug"]] = domain
        return domains

    def _seed_methods(self):
        methods = {}
        for row in METHOD_SEEDS:
            method, created = NLPMethod.objects.get_or_create(
                slug=row["slug"],
                defaults={"name_en": row["name_en"], "name_ar": row["name_ar"]},
            )
            if not created and (
                method.name_en != row["name_en"] or method.name_ar != row["name_ar"]
            ):
                method.name_en = row["name_en"]
                method.name_ar = row["name_ar"]
                method.save(update_fields=["name_en", "name_ar"])
            methods[row["slug"]] = method
        return methods

    def _seed_institutions(self, countries, specialties, admin, reset):
        institutions = {}
        for index, row in enumerate(INSTITUTION_SEEDS, start=1):
            country = countries[row["country_code"]]
            inst, created = Institution.objects.get_or_create(
                name=row["name_en"],
                country=country,
                defaults={
                    "name_ar": row["name_ar"],
                    "name_en": row["name_en"],
                    "acronym": row["acronym"],
                    "type": row["type"],
                    "city": row["city_en"],
                    "city_ar": row["city_ar"],
                    "city_en": row["city_en"],
                    "website": row.get("website", ""),
                    "created_by": admin,
                    "approval_status": "approved",
                    "description_ar": "مؤسسة بحثية أو جامعية نشطة في أبحاث معالجة اللغة العربية والذكاء الاصطناعي.",
                    "description_en": "A research-oriented institution active in Arabic NLP and AI research.",
                    "address_ar": f"{row['city_ar']}, {row['name_ar']}",
                    "address_en": f"{row['city_en']}, {row['name_en']}",
                },
            )
            changed = False
            for field_name in [
                "name_ar",
                "name_en",
                "acronym",
                "type",
                "city",
                "city_ar",
                "city_en",
                "website",
                "approval_status",
                "description_ar",
                "description_en",
                "address_ar",
                "address_en",
            ]:
                value = row.get(field_name) if field_name in row else None
                if field_name == "approval_status":
                    value = "approved"
                elif field_name == "description_ar":
                    value = "مؤسسة بحثية أو جامعية نشطة في أبحاث معالجة اللغة العربية والذكاء الاصطناعي."
                elif field_name == "description_en":
                    value = "A research-oriented institution active in Arabic NLP and AI research."
                elif field_name == "address_ar":
                    value = f"{row['city_ar']}, {row['name_ar']}"
                elif field_name == "address_en":
                    value = f"{row['city_en']}, {row['name_en']}"
                elif field_name not in row:
                    continue
                if getattr(inst, field_name) != value:
                    setattr(inst, field_name, value)
                    changed = True
            if inst.created_by_id != admin.id:
                inst.created_by = admin
                changed = True
            if changed:
                inst.save()
            inst.specialties.set([specialties[code] for code in row["specialties"]])
            institutions[row["acronym"]] = inst
            alias_map = {
                "CU": ["CAIRO"],
                "AU": ["ALEX"],
                "ASU": ["AINSHAMS"],
                "UM5": ["UQAM"],
                "KAUST": ["UBC"],
            }
            for alias in alias_map.get(row["acronym"], []):
                institutions[alias] = inst
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} institutions...")
        return institutions

    def _pick_institutions(self, institutions, acronyms):
        return [institutions[code] for code in acronyms if code in institutions]

    def _seed_users(self, institutions, domains, reset):
        users = []
        speciality_cycle = cycle(list(SPECIALTY_SEEDS))
        institution_cycle = cycle(list(institutions.values()))
        for index, row in enumerate(RESEARCHER_SEEDS, start=1):
            email = f"{slug_for(row['name_en'])}@sanad.dz"
            institution = institutions.get(
                row["institution_code"], next(institution_cycle)
            )
            specialty = next(speciality_cycle)
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": row["name_en"],
                    "full_name_en": row["name_en"],
                    "full_name_ar": row["name_ar"],
                    "bio": "",
                    "bio_en": f"Researcher in Arabic NLP, with a focus on {specialty['name_en'].lower()} and reproducible benchmarks.",
                    "bio_ar": f"باحث في معالجة اللغة العربية مع تركيز على {specialty['name_ar']} وبناء موارد قابلة لإعادة الاستخدام.",
                    "institution": institution,
                    "status": "active",
                    "is_verified": True,
                    "is_email_verified": True,
                    "is_active": True,
                    "show_online_status": True,
                },
            )
            changed = False
            for field_name, value in [
                ("full_name", row["name_en"]),
                ("full_name_en", row["name_en"]),
                ("full_name_ar", row["name_ar"]),
                (
                    "bio_en",
                    f"Researcher in Arabic NLP, with a focus on {specialty['name_en'].lower()} and reproducible benchmarks.",
                ),
                (
                    "bio_ar",
                    f"باحث في معالجة اللغة العربية مع تركيز على {specialty['name_ar']} وبناء موارد قابلة لإعادة الاستخدام.",
                ),
                ("institution", institution),
                ("status", "active"),
                ("is_verified", True),
                ("is_email_verified", True),
                ("is_active", True),
                ("show_online_status", True),
            ]:
                if getattr(user, field_name) != value:
                    setattr(user, field_name, value)
                    changed = True
            if changed:
                user.save()
            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "bio": f"Arabic NLP researcher based at {institution.name_en}.",
                    "orcid": None,
                    "github_username": slug_for(row["name_en"]),
                    "institution": institution,
                    "is_independent": False,
                    "country": institution.country.name_en,
                    "show_online_status": True,
                },
            )
            profile.bio = f"Arabic NLP researcher based at {institution.name_en}."
            profile.github_username = slug_for(row["name_en"])
            profile.institution = institution
            profile.country = institution.country.name_en
            profile.show_online_status = True
            profile.save()
            profile.expertise_tags.set(
                [
                    domains["arabic-nlp"],
                    domains.get("sentiment-analysis", domains["arabic-nlp"]),
                ]
            )
            users.append(user)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} users...")
        return users

    def _seed_datasets(self, reset):
        datasets = []
        for base, variant in product(DATASET_BASES, DATASET_VARIANTS):
            title = f"{base['name']} {variant['suffix']}"
            obj, created = Dataset.objects.get_or_create(
                name=title,
                defaults={
                    "huggingface_id": None,
                    "paperswithcode_id": None,
                    "language": "ar",
                    "description_en": f"{base['description_en']} This edition is curated for {variant['suffix'].lower()}.",
                    "description_ar": f"{base['description_ar']} وتمت تهيئته لاختبار {variant['suffix']}.",
                },
            )
            obj.description_en = f"{base['description_en']} This edition is curated for {variant['suffix'].lower()}."
            obj.description_ar = (
                f"{base['description_ar']} وتمت تهيئته لاختبار {variant['suffix']}."
            )
            obj.language = "ar"
            obj.save()
            datasets.append(obj)
        self.stdout.write(
            self.style.SUCCESS(f"  Created/updated {len(datasets)} datasets...")
        )
        return datasets

    def _seed_corpora(self, reset):
        corpora = []
        for base, variant in product(CORPUS_BASES, CORPUS_VARIANTS):
            title = f"{base['name']} {variant['suffix']}"
            obj, created = Corpus.objects.get_or_create(
                title=title,
                defaults={
                    "title_ar": f"{base['name']} {variant['suffix']}",
                    "title_en": title,
                    "description": f"{base['description_ar']} {variant['suffix']}.",
                    "description_ar": f"{base['description_ar']} {variant['suffix']}.",
                    "description_en": f"{base['description_en']} {variant['suffix']}.",
                    "author": self._get_or_create_admin(),
                    "field": FieldChoices.CORPUS_LINGUISTICS,
                    "language": "ar",
                    "approval_status": "approved",
                    "is_approved": True,
                },
            )
            obj.title_ar = f"{base['name']} {variant['suffix']}"
            obj.title_en = title
            obj.description = f"{base['description_ar']} {variant['suffix']}."
            obj.description_ar = f"{base['description_ar']} {variant['suffix']}."
            obj.description_en = f"{base['description_en']} {variant['suffix']}."
            obj.author = self._get_or_create_admin()
            obj.field = FieldChoices.CORPUS_LINGUISTICS
            obj.language = "ar"
            obj.approval_status = "approved"
            obj.is_approved = True
            obj.save()
            corpora.append(obj)
        self.stdout.write(
            self.style.SUCCESS(f"  Created/updated {len(corpora)} corpora...")
        )
        return corpora

    def _seed_tools(self, admin, reset):
        tools = []
        for base, variant in product(TOOL_BASES, TOOL_VARIANTS):
            title = f"{base['name']} {variant['suffix']}"
            obj, created = NLPTool.objects.get_or_create(
                title=title,
                defaults={
                    "title_ar": title,
                    "title_en": title,
                    "description": f"{base['name']} configured for Arabic {variant['use_case']} workflows.",
                    "description_ar": f"تم تهيئة {base['name']} لدعم مسارات {variant['use_case']} العربية.",
                    "author": admin,
                    "language": "ar",
                    "approval_status": "approved",
                    "is_approved": True,
                    "tool_type": base["tool_type"],
                    "version": base["version"],
                    "documentation_link": f"https://example.org/{slugify(base['name'])}",
                    "github_url": f"https://github.com/{slugify(base['organization']).replace('-', '')}/{slugify(base['name'])}",
                    "demo_url": f"https://demo.example.org/{slugify(base['name'])}",
                    "paper_url": "",
                    "license": "Apache-2.0",
                    "stars_count": 1000 + len(tools) * 7,
                    "last_updated": date.today() - timedelta(days=len(tools) * 11),
                    "installation_instructions": f"Install {base['name']} and run the Arabic {variant['use_case']} pipeline using the official configuration.",
                    "use_cases": [
                        "Arabic text processing",
                        variant["use_case"],
                        "benchmark evaluation",
                    ],
                    "author_organization": base["organization"],
                    "source_url": f"https://example.org/{slugify(base['name'])}",
                    "source_name": base["organization"],
                    "supported_languages": "ar",
                },
            )
            obj.title_ar = title
            obj.title_en = title
            obj.description = (
                f"{base['name']} configured for Arabic {variant['use_case']} workflows."
            )
            obj.description_ar = (
                f"تم تهيئة {base['name']} لدعم مسارات {variant['use_case']} العربية."
            )
            obj.author = admin
            obj.language = "ar"
            obj.approval_status = "approved"
            obj.is_approved = True
            obj.tool_type = base["tool_type"]
            obj.version = base["version"]
            obj.documentation_link = f"https://example.org/{slugify(base['name'])}"
            obj.github_url = f"https://github.com/{slugify(base['organization']).replace('-', '')}/{slugify(base['name'])}"
            obj.demo_url = f"https://demo.example.org/{slugify(base['name'])}"
            obj.license = "Apache-2.0"
            obj.stars_count = 1000 + len(tools) * 7
            obj.last_updated = date.today() - timedelta(days=len(tools) * 11)
            obj.installation_instructions = f"Install {base['name']} and run the Arabic {variant['use_case']} pipeline using the official configuration."
            obj.use_cases = [
                "Arabic text processing",
                variant["use_case"],
                "benchmark evaluation",
            ]
            obj.author_organization = base["organization"]
            obj.source_url = f"https://example.org/{slugify(base['name'])}"
            obj.source_name = base["organization"]
            obj.supported_languages = "ar"
            obj.save()
            tools.append(obj)
        self.stdout.write(
            self.style.SUCCESS(f"  Created/updated {len(tools)} tools...")
        )
        return tools

    def _seed_courses(self, users, institutions, reset):
        courses = []
        teacher_cycle = cycle(users)
        for index, (theme, institution) in enumerate(
            product(COURSE_THEMES, institutions), start=1
        ):
            teacher = next(teacher_cycle)
            title = f"{theme['title']} at {institution.acronym}"
            obj, created = Course.objects.get_or_create(
                title=title,
                teacher=teacher,
                institution=institution,
                academic_year="2024-2025",
                defaults={
                    "title_ar": title,
                    "title_en": title,
                    "description": f"Structured course on {theme['title']} for Arabic NLP practitioners.",
                    "description_ar": f"مقرر منظم حول {theme['title']} للباحثين والممارسين في معالجة اللغة العربية.",
                    "author": teacher,
                    "field": theme["field"],
                    "academic_level": theme["level"],
                    "prerequisites": "Python, statistics, and introductory machine learning.",
                    "syllabus": "Tokenization, morphology, transformers, evaluation, and reproducible Arabic NLP experiments.",
                    "platform": "university",
                    "is_free": True,
                    "certificate_available": True,
                    "approval_status": "approved",
                    "is_approved": True,
                    "language": "ar",
                },
            )
            obj.title_ar = title
            obj.title_en = title
            obj.description = (
                f"Structured course on {theme['title']} for Arabic NLP practitioners."
            )
            obj.description_ar = f"مقرر منظم حول {theme['title']} للباحثين والممارسين في معالجة اللغة العربية."
            obj.author = teacher
            obj.field = theme["field"]
            obj.academic_level = theme["level"]
            obj.prerequisites = "Python, statistics, and introductory machine learning."
            obj.syllabus = "Tokenization, morphology, transformers, evaluation, and reproducible Arabic NLP experiments."
            obj.platform = "university"
            obj.is_free = True
            obj.certificate_available = True
            obj.approval_status = "approved"
            obj.is_approved = True
            obj.language = "ar"
            obj.academic_year = "2024-2025"
            obj.save()
            courses.append(obj)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} courses...")
        return courses

    def _seed_articles(self, users, institutions, reset):
        documents = []
        articles = []
        journal_cycle = cycle(
            [
                "ACL 2025 Proceedings",
                "EMNLP 2025 Proceedings",
                "COLING 2025 Proceedings",
                "WANLP 2025 Proceedings",
            ]
        )
        author_cycle = cycle(users)
        venues = [
            {
                "title": "Dialect-aware Arabic NER with Transformers",
                "description": "A reproducible study on Arabic scientific entity recognition with transformer encoders.",
                "description_ar": "دراسة قابلة لإعادة الإنتاج حول التعرف على الكيانات العربية العلمية باستخدام المحولات.",
            },
            {
                "title": "Arabic Sentiment Analysis over Social Media",
                "description": "Benchmarking robust sentiment models for Arabic social platforms.",
                "description_ar": "قياس متانة نماذج تحليل المشاعر على المنصات العربية الاجتماعية.",
            },
            {
                "title": "Machine Translation for Arabic Dialects",
                "description": "Comparative evaluation of dialect-to-MSA translation pipelines.",
                "description_ar": "تقييم مقارن لمسارات الترجمة من اللهجات العربية إلى الفصحى.",
            },
            {
                "title": "Diacritization of Arabic News Texts",
                "description": "Automated diacritization strategies for editorial and journalistic Arabic.",
                "description_ar": "استراتيجيات التشكيل الآلي للنصوص العربية الصحفية.",
            },
            {
                "title": "Arabic Question Answering for Scholarly Resources",
                "description": "Question answering over academic and institutional Arabic collections.",
                "description_ar": "نظم الإجابة عن الأسئلة على المجموعات الأكاديمية والمؤسساتية العربية.",
            },
            {
                "title": "Summarization of Arabic News Articles",
                "description": "Extractive and abstractive summarization for large Arabic news streams.",
                "description_ar": "تلخيص استخلاصي وتوليدي لأخبار عربية واسعة النطاق.",
            },
            {
                "title": "Morphological Tagging for Arabic Scientific Text",
                "description": "High-accuracy tagging of technical Arabic writing in scholarly contexts.",
                "description_ar": "وسم صرفي عالي الدقة للنصوص العلمية العربية.",
            },
            {
                "title": "Benchmarking Arabic LLMs on Evaluation Suites",
                "description": "A rigorous evaluation of Arabic large language models across tasks.",
                "description_ar": "تقييم صارم للنماذج اللغوية العربية الكبيرة عبر مهام متعددة.",
            },
            {
                "title": "Cross-dialect Normalization for Arabic Pipelines",
                "description": "Normalization strategies that improve downstream Arabic NLP quality.",
                "description_ar": "استراتيجيات التطبيع التي تحسن جودة التطبيقات اللاحقة لمعالجة العربية.",
            },
            {
                "title": "Corpus Cleaning for Arabic News and Reviews",
                "description": "Noise reduction and quality filtering for Arabic corpora.",
                "description_ar": "خفض الضجيج وترشيح الجودة في المدونات العربية.",
            },
        ]
        for index, (theme, institution) in enumerate(
            product(venues, institutions[:4]), start=1
        ):
            author = next(author_cycle)
            title = f"{theme['title']} - {institution.acronym}"
            document, created = Document.objects.get_or_create(
                title=title,
                author=author,
                document_type="article",
                defaults={
                    "title_ar": title,
                    "title_en": title,
                    "description": theme["description"],
                    "description_ar": theme["description_ar"],
                    "description_en": theme["description"],
                    "approval_status": "approved",
                    "is_approved": True,
                    "language": "ar",
                    "entities": {"venue": institution.acronym},
                },
            )
            document.title_ar = title
            document.title_en = title
            document.description = theme["description"]
            document.description_ar = theme["description_ar"]
            document.description_en = theme["description"]
            document.author = author
            document.document_type = "article"
            document.approval_status = "approved"
            document.is_approved = True
            document.language = "ar"
            document.entities = {"venue": institution.acronym}
            document.save()
            coauthors = [author]
            if len(users) > 1:
                coauthors.append(users[(index + 1) % len(users)])
            document.authors.set(coauthors)

            article, article_created = Article.objects.get_or_create(
                document=document,
                defaults={
                    "doi": f"10.1234/sanad.{index:04d}",
                    "journal": next(journal_cycle),
                    "publication_date": date.today() - timedelta(days=90 + index),
                },
            )
            article.doi = f"10.1234/sanad.{index:04d}"
            article.journal = next(journal_cycle)
            article.publication_date = date.today() - timedelta(days=90 + index)
            article.save()

            documents.append(document)
            articles.append(article)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} articles...")
        return documents, articles

    def _seed_projects(self, users, institutions, domains, methods, datasets, reset):
        projects = []
        project_methods = list(methods.values())
        project_domains = list(domains.values())
        dataset_cycle = cycle(datasets)
        for index, (theme, institution) in enumerate(
            product(PROJECT_THEMES, institutions), start=1
        ):
            coordinator = users[index % len(users)]
            title = f"{theme['title']} at {institution.acronym}"
            project, created = Project.objects.get_or_create(
                title=title,
                institution=institution,
                coordinator=coordinator,
                defaults={
                    "title_ar": title,
                    "title_en": title,
                    "description": f"A research project focused on {theme['title'].lower()} within Arabic NLP.",
                    "description_ar": f"مشروع بحثي يركز على {theme['title']} ضمن معالجة اللغة العربية.",
                    "status": "ongoing" if index % 3 else "planned",
                    "approval_status": "approved",
                    "is_approved": True,
                    "date_start": date.today() - timedelta(days=30 + index),
                    "date_end": date.today() + timedelta(days=180 + index),
                },
            )
            project.title_ar = title
            project.title_en = title
            project.description = f"A research project focused on {theme['title'].lower()} within Arabic NLP."
            project.description_ar = (
                f"مشروع بحثي يركز على {theme['title']} ضمن معالجة اللغة العربية."
            )
            project.status = "ongoing" if index % 3 else "planned"
            project.approval_status = "approved"
            project.is_approved = True
            project.date_start = date.today() - timedelta(days=30 + index)
            project.date_end = date.today() + timedelta(days=180 + index)
            project.save()
            domain_objs = [
                domains[slug] for slug in theme["domain_slugs"] if slug in domains
            ]
            method_objs = [
                methods[slug] for slug in theme["method_slugs"] if slug in methods
            ]
            dataset_objs = []
            for _ in range(2):
                dataset_objs.append(next(dataset_cycle))
            project.research_domains.set(domain_objs)
            project.nlp_methods.set(method_objs)
            project.datasets.set(dataset_objs)
            projects.append(project)

            for member_index in range(2):
                member = users[(index + member_index + 1) % len(users)]
                ProjectMember.objects.get_or_create(
                    project=project,
                    member=member,
                    defaults={
                        "role": "Co-investigator"
                        if member_index == 0
                        else "Research assistant",
                        "status": "accepted",
                        "leave_request_status": "none",
                    },
                )
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} projects...")
        return projects

    def _seed_events(self, users, institutions, admin, reset):
        events = []
        organizer_cycle = cycle(institutions)
        creator_cycle = cycle(users)
        for index, (theme, institution) in enumerate(
            product(EVENT_THEMES, institutions), start=1
        ):
            organizer = institution
            creator = next(creator_cycle)
            title = f"{theme['title']} at {institution.acronym}"
            event, created = Event.objects.get_or_create(
                title=title,
                organizer=organizer,
                start_date=date.today() + timedelta(days=30 + index),
                defaults={
                    "title_ar": title,
                    "title_en": title,
                    "description": f"A professionally curated Arabic NLP event linked to {theme['title']}.",
                    "description_ar": f"فعالية مهنية في معالجة اللغة العربية مرتبطة بـ {theme['title']}.",
                    "event_type": theme["event_type"],
                    "domains": "arabic_nlp,computational_linguistics,ai",
                    "location": institution.city_en,
                    "location_ar": institution.city_ar,
                    "location_en": institution.city_en,
                    "is_approved": True,
                    "approval_status": "approved",
                    "scrape_status": Event.SCRAPE_STATUS_APPROVED,
                    "validation_notes": "Seeded for Arabic NLP research cataloguing.",
                    "confidence_score": 0.95,
                    "submission_deadline": date.today() + timedelta(days=10 + index),
                    "end_date": date.today() + timedelta(days=31 + index),
                    "website": institution.website or "https://example.org",
                    "registration_link": f"https://example.org/register/{slugify(title)}",
                    "is_online": index % 4 == 0,
                    "is_hybrid": index % 5 == 0,
                    "source_url": institution.website or "https://example.org",
                    "source_name": institution.acronym,
                    "last_scraped_at": timezone.now(),
                    "update_count": 1,
                    "is_past_event": False,
                    "language": theme["language"],
                    "tags": {
                        "theme": theme["title"],
                        "institution": institution.acronym,
                    },
                    "entities": {"institution": institution.acronym},
                    "created_by": creator,
                    "approval_date": timezone.now(),
                    "approved_by": admin,
                    "contact_email": f"events@{institution.acronym.lower()}.edu",
                },
            )
            event.title_ar = title
            event.title_en = title
            event.description = (
                f"A professionally curated Arabic NLP event linked to {theme['title']}."
            )
            event.description_ar = (
                f"فعالية مهنية في معالجة اللغة العربية مرتبطة بـ {theme['title']}."
            )
            event.event_type = theme["event_type"]
            event.domains = "arabic_nlp,computational_linguistics,ai"
            event.location = institution.city_en
            event.location_ar = institution.city_ar
            event.location_en = institution.city_en
            event.is_approved = True
            event.approval_status = "approved"
            event.scrape_status = Event.SCRAPE_STATUS_APPROVED
            event.validation_notes = "Seeded for Arabic NLP research cataloguing."
            event.confidence_score = 0.95
            event.submission_deadline = date.today() + timedelta(days=10 + index)
            event.end_date = date.today() + timedelta(days=31 + index)
            event.website = institution.website or "https://example.org"
            event.registration_link = f"https://example.org/register/{slugify(title)}"
            event.is_online = index % 4 == 0
            event.is_hybrid = index % 5 == 0
            event.source_url = institution.website or "https://example.org"
            event.source_name = institution.acronym
            event.last_scraped_at = timezone.now()
            event.update_count = 1
            event.is_past_event = False
            event.language = theme["language"]
            event.tags = {"theme": theme["title"], "institution": institution.acronym}
            event.entities = {"institution": institution.acronym}
            event.created_by = creator
            event.approved_by = admin
            event.approval_date = timezone.now()
            event.contact_email = f"events@{institution.acronym.lower()}.edu"
            event.save()
            events.append(event)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} events...")
        return events

    def _seed_opportunities(self, users, institutions, admin, reset):
        opportunities = []
        for index, (theme, institution) in enumerate(
            product(OPPORTUNITY_THEMES, institutions), start=1
        ):
            creator = users[index % len(users)]
            title = f"{theme['title']} at {institution.acronym}"
            opportunity, created = Opportunity.objects.get_or_create(
                title_en=title,
                created_by=creator,
                deadline=date.today() + timedelta(days=20 + index),
                defaults={
                    "title_ar": title,
                    "title": title,
                    "opportunity_type": theme["opportunity_type"],
                    "institution": institution,
                    "organization_en": institution.name_en,
                    "organization_ar": institution.name_ar,
                    "location": institution.city_en,
                    "mode": theme["mode"],
                    "level": theme["level"],
                    "description": f"{theme['title']} focused on Arabic NLP research, data curation, and reproducible experimentation.",
                    "skills": ["Arabic NLP", "Python", "research writing"],
                    "contact": f"careers@{institution.acronym.lower()}.edu",
                    "status": "approved",
                    "scrape_status": Opportunity.SCRAPE_STATUS_APPROVED,
                    "validation_notes": "Seeded opportunity for the Arabic NLP catalog.",
                    "confidence_score": 0.96,
                    "last_scraped_at": timezone.now(),
                    "update_counter": 1,
                    "approval_status": "approved",
                    "is_published": True,
                    "user_role": "user",
                    "approved_by": admin,
                    "approved_at": timezone.now(),
                    "rejection_reason": "",
                },
            )
            opportunity.title = title
            opportunity.title_en = title
            opportunity.title_ar = title
            opportunity.opportunity_type = theme["opportunity_type"]
            opportunity.institution = institution
            opportunity.organization_en = institution.name_en
            opportunity.organization_ar = institution.name_ar
            opportunity.location = institution.city_en
            opportunity.mode = theme["mode"]
            opportunity.level = theme["level"]
            opportunity.description = f"{theme['title']} focused on Arabic NLP research, data curation, and reproducible experimentation."
            opportunity.skills = ["Arabic NLP", "Python", "research writing"]
            opportunity.contact = f"careers@{institution.acronym.lower()}.edu"
            opportunity.status = "approved"
            opportunity.scrape_status = Opportunity.SCRAPE_STATUS_APPROVED
            opportunity.validation_notes = (
                "Seeded opportunity for the Arabic NLP catalog."
            )
            opportunity.confidence_score = 0.96
            opportunity.last_scraped_at = timezone.now()
            opportunity.update_counter = 1
            opportunity.approval_status = "approved"
            opportunity.is_published = True
            opportunity.user_role = "user"
            opportunity.approved_by = admin
            opportunity.approved_at = timezone.now()
            opportunity.rejection_reason = ""
            opportunity.save()
            opportunities.append(opportunity)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} opportunities...")
        return opportunities

    def _seed_news(self, users, institutions, reset):
        news_items = []
        creator_cycle = cycle(users)
        for index, (theme, institution) in enumerate(
            product(NEWS_THEMES, institutions), start=1
        ):
            creator = next(creator_cycle)
            title = f"{theme['title']} at {institution.acronym}"
            abstract = (
                f"This bulletin documents an Arabic NLP development led by {institution.name_en}. "
                f"It covers dataset curation, benchmark design, evaluation methodology, and the release of reproducible assets for researchers across the Arabic NLP ecosystem. "
                f"The update is aligned with professional research communication standards and is ready for publication in a platform news feed."
            )
            news, created = NewsPublication.objects.get_or_create(
                title=title,
                created_by=creator,
                year=2024 + (index % 2),
                defaults={
                    "type": theme["type"],
                    "abstract": abstract,
                    "authors": [creator.full_name_en, institution.name_en],
                    "affiliations": institution.name_en,
                    "venue": theme["venue"],
                    "nlp_tasks": ["Arabic NLP", "benchmarking"],
                    "languages": ["Arabic", "English"],
                    "keywords": ["Arabic NLP", "research update", institution.acronym],
                    "status": "published",
                },
            )
            news.type = theme["type"]
            news.abstract = abstract
            news.authors = [creator.full_name_en, institution.name_en]
            news.affiliations = institution.name_en
            news.venue = theme["venue"]
            news.nlp_tasks = ["Arabic NLP", "benchmarking"]
            news.languages = ["Arabic", "English"]
            news.keywords = ["Arabic NLP", "research update", institution.acronym]
            news.status = "published"
            news.save()
            news_items.append(news)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} news entries...")
        return news_items

    def _seed_forum(self, users, institutions, projects, events, posts, reset):
        topics = []
        topic_cycle = cycle(users)
        for index, (theme, institution) in enumerate(
            product(FORUM_THEMES, institutions), start=1
        ):
            creator = next(topic_cycle)
            title = f"{theme['title']} - {institution.acronym}"
            topic, created = Topic.objects.get_or_create(
                title=title,
                creator=creator,
                defaults={
                    "title_ar": title,
                    "title_en": title,
                    "description": theme["description"],
                    "description_ar": f"{theme['description']} (مجموعة نقاش مهنية).",
                    "description_en": theme["description"],
                    "approval_status": "approved",
                    "is_approved": True,
                    "related_project": projects[index % len(projects)]
                    if projects
                    else None,
                    "related_event": events[index % len(events)] if events else None,
                    "related_news": posts[index % len(posts)] if posts else None,
                },
            )
            topic.title_ar = title
            topic.title_en = title
            topic.description = theme["description"]
            topic.description_ar = f"{theme['description']} (مجموعة نقاش مهنية)."
            topic.description_en = theme["description"]
            topic.approval_status = "approved"
            topic.is_approved = True
            topic.related_project = (
                projects[index % len(projects)] if projects else None
            )
            topic.related_event = events[index % len(events)] if events else None
            topic.related_news = posts[index % len(posts)] if posts else None
            topic.save()

            chatroom, _ = ChatRoom.objects.get_or_create(
                topic=topic,
                name=f"{title} Room",
                defaults={
                    "name_ar": f"{title} غرفة",
                    "name_en": f"{title} Room",
                    "description": f"Professional discussion room for {theme['title']}.",
                    "description_ar": f"غرفة نقاش مهنية حول {theme['title']}.",
                    "description_en": f"Professional discussion room for {theme['title']}.",
                    "creator": creator,
                },
            )
            chatroom.name_ar = f"{title} غرفة"
            chatroom.name_en = f"{title} Room"
            chatroom.description = f"Professional discussion room for {theme['title']}."
            chatroom.description_ar = f"غرفة نقاش مهنية حول {theme['title']}."
            chatroom.description_en = (
                f"Professional discussion room for {theme['title']}."
            )
            chatroom.creator = creator
            chatroom.save()

            Message.objects.get_or_create(
                chatroom=chatroom,
                user=creator,
                content=f"We should align annotation guidelines with the latest Arabic NLP benchmark for {institution.acronym}.",
                defaults={"is_edited": False},
            )
            Message.objects.get_or_create(
                chatroom=chatroom,
                user=users[(index + 1) % len(users)],
                content="The evaluation protocol should include dialectal variation, strong baselines, and clear reporting of error analysis.",
                defaults={"is_edited": False},
            )
            topics.append(topic)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} forum topics...")
        return topics

    def _seed_feed(self, users, institutions, reset):
        posts = []
        commenter_cycle = cycle(users)
        for index, (theme, institution) in enumerate(
            product(FEED_THEMES, institutions), start=1
        ):
            author = users[index % len(users)]
            title_en = f"{theme['title']} at {institution.acronym}"
            title_ar = title_en
            content_en = (
                f"{theme['title']} documents a professional update from {institution.name_en}. "
                f"The note summarizes Arabic NLP progress, benchmark status, and collaboration opportunities for researchers working on Arabic language technologies."
            )
            content_ar = (
                f"{theme['title']} يقدّم تحديثاً مهنياً من {institution.name_ar}. "
                f"وتلخص هذه المداخلة تقدم أبحاث معالجة اللغة العربية، وحالة المعايير المرجعية، وفرص التعاون بين الباحثين."
            )
            post, created = Post.objects.get_or_create(
                author=author,
                title_en=title_en,
                title_ar=title_ar,
                defaults={
                    "title": title_en,
                    "content": content_en,
                    "content_ar": content_ar,
                    "content_en": content_en,
                    "news_category": theme["category"],
                    "approval_status": "approved",
                    "scrape_status": Post.SCRAPE_STATUS_APPROVED,
                    "validation_notes": "Seeded community post.",
                    "confidence_score": 0.94,
                    "rejection_reason": "",
                    "view_count": 0,
                },
            )
            post.title = title_en
            post.title_en = title_en
            post.title_ar = title_ar
            post.content = content_en
            post.content_ar = content_ar
            post.content_en = content_en
            post.news_category = theme["category"]
            post.approval_status = "approved"
            post.scrape_status = Post.SCRAPE_STATUS_APPROVED
            post.validation_notes = "Seeded community post."
            post.confidence_score = 0.94
            post.rejection_reason = ""
            post.save()
            liked_users = [
                users[(index + offset) % len(users)] for offset in range(1, 4)
            ]
            post.likes.set(liked_users)
            Comment.objects.get_or_create(
                post=post,
                author=next(commenter_cycle),
                content=f"This is a valuable update for Arabic NLP researchers working on {institution.acronym} collaborations.",
            )
            posts.append(post)
            if index % 10 == 0:
                self.stdout.write(f"  Created/updated {index} feed posts...")
        return posts
