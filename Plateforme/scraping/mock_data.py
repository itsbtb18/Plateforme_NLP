import datetime

# Realistic Institutions and Organizations
INSTITUTIONS = [
    {
        "name_en": "University of Science and Technology Houari Boumediene (USTHB)",
        "name_ar": "جامعة العلوم والتكنولوجيا هواري بومدين",
        "city": "Algiers",
        "city_ar": "الجزائر العاصمة",
        "website": "https://www.usthb.dz",
        "domain": "usthb.dz",
        "inst_type": "University",
        "acronym": "USTHB",
    },
    {
        "name_en": "New York University Abu Dhabi",
        "name_ar": "جامعة نيويورك أبوظبي",
        "city": "Abu Dhabi",
        "city_ar": "أبوظبي",
        "website": "https://nyuad.nyu.edu",
        "domain": "nyu.edu",
        "inst_type": "University",
        "acronym": "NYUAD",
    },
    {
        "name_en": "Qatar Computing Research Institute",
        "name_ar": "معهد قطر لبحوث الحوسبة",
        "city": "Doha",
        "city_ar": "الدوحة",
        "website": "https://www.qcri.org",
        "domain": "qcri.org",
        "inst_type": "Research Institute",
        "acronym": "QCRI",
    },
    {
        "name_en": "King Saud University",
        "name_ar": "جامعة الملك سعود",
        "city": "Riyadh",
        "city_ar": "الرياض",
        "website": "https://ksu.edu.sa",
        "domain": "ksu.edu.sa",
        "inst_type": "University",
        "acronym": "KSU",
    },
    {
        "name_en": "University of Carthage",
        "name_ar": "جامعة قرطاج",
        "city": "Tunis",
        "city_ar": "تونس",
        "website": "http://www.ucar.rnu.tn",
        "domain": "ucar.rnu.tn",
        "inst_type": "University",
        "acronym": "UCAR",
    },
    {
        "name_en": "Birzeit University",
        "name_ar": "جامعة بيرزيت",
        "city": "Ramallah",
        "city_ar": "رام الله",
        "website": "https://www.birzeit.edu",
        "domain": "birzeit.edu",
        "inst_type": "University",
        "acronym": "BZU",
    },
    {
        "name_en": "Cairo University",
        "name_ar": "جامعة القاهرة",
        "city": "Giza",
        "city_ar": "الجيزة",
        "website": "https://cu.edu.eg",
        "domain": "cu.edu.eg",
        "inst_type": "University",
        "acronym": "CU",
    },
    {
        "name_en": "American University of Beirut",
        "name_ar": "الجامعة الأمريكية في بيروت",
        "city": "Beirut",
        "city_ar": "بيروت",
        "website": "https://www.aub.edu.lb",
        "domain": "aub.edu.lb",
        "inst_type": "University",
        "acronym": "AUB",
    },
    {
        "name_en": "Masdar Institute",
        "name_ar": "معهد مصدر للعلوم والتكنولوجيا",
        "city": "Abu Dhabi",
        "city_ar": "أبوظبي",
        "website": "https://www.masdar.ac.ae",
        "domain": "masdar.ac.ae",
        "inst_type": "Research Institute",
        "acronym": "MI",
    },
    {
        "name_en": "King Abdullah University of Science and Technology (KAUST)",
        "name_ar": "جامعة الملك عبد الله للعلوم والتقنية",
        "city": "Thuwal",
        "city_ar": "ثول",
        "website": "https://www.kaust.edu.sa",
        "domain": "kaust.edu.sa",
        "inst_type": "University",
        "acronym": "KAUST",
    },
]

INSTRUCTORS = [
    "Dr. Amina Haddad",
    "Prof. Karim Belkacem",
    "Dr. Sarah Al-Mansoori",
    "Prof. Yassine Ben Amor",
    "Dr. Layla Al-Farsi",
    "Prof. Tariq Al-Jamil",
    "Dr. Fatma Zahra",
    "Prof. Mourad Oussalah",
    "Dr. Hanan Al-Mubarak",
    "Prof. Khaled Abdel-Fattah",
]

def get_mock_items_for_category(category: str) -> list[dict]:
    category = category.lower().strip()
    items = []

    # Dynamic pool definitions for combinatorics (10x10 = 100 unique combinations)
    
    # 1. CORPUS (DATASETS)
    DIALECTS = ["Algerian Darja", "Modern Standard Arabic", "Classical Arabic", "Tunisian Dialect", "Egyptian Arabic", "Levantine Arabic", "Gulf Arabic", "Moroccan Darja", "Yemeni Arabic", "Iraqi Dialect"]
    DIALECTS_AR = ["الدرجة الجزائرية", "اللغة العربية الفصحى الحديثة", "اللغة العربية الكلاسيكية", "اللهجة التونسية", "العربية المصرية", "العربية الشامية", "العربية الخليجية", "الدرجة المغربية", "العربية اليمنية", "اللهجة العراقية"]

    SOURCES = ["Twitter/X Posts", "Wikipedia Articles", "News Portals", "Historical Manuscripts", "Legal Documents", "Customer Reviews", "YouTube Transcripts", "Podcast Audio", "Web Scraped Text", "Speech Recordings"]
    SOURCES_AR = ["منشورات تويتر/إكس", "مقالات ويكيبيديا", "البوابات الإخبارية", "المخطوطات التاريخية", "الوثائق القانونية", "آراء العملاء", "نصوص اليوتيوب", "المقاطع الصوتية للبودكاست", "نصوص مجمعة من الويب", "تسجيلات كلامية"]

    TASKS = ["Sentiment Analysis", "Named Entity Recognition", "Part-of-Speech Tagging", "Machine Translation", "Question Answering", "Text Summarization", "Dialect Identification", "Dependency Parsing", "Speech Recognition", "Coreference Resolution"]
    TASKS_AR = ["تحليل المشاعر", "التعرف على الكيانات المسماة", "وسم أجزاء الكلام", "الترجمة الآلية", "الإجابة على الأسئلة", "تلخيص النصوص", "تحديد اللهجات", "التحليل الإعرابي التبعي", "التعرف على الكلام", "حل المراجع المشتركة"]

    FORMATS = ["Corpus", "Dataset", "Treebank", "Parallel Text", "Speech Database", "Lexicon", "Diacritized Text", "Dialogue Transcript", "Benchmarking Suite", "Text Collection"]
    FORMATS_AR = ["مدونة", "مجموعة بيانات", "بنك شجري", "نص متوازٍ", "قاعدة بيانات كلامية", "معجم", "نص مشكول", "نص حواري", "مجموعة اختبار قياسية", "مجموعة نصوص"]

    # 2. TOOLS
    NAMES = ["Ara", "Camel", "Farasa", "Noor", "Qalsadi", "Barq", "Sahar", "Sindibad", "Fehris", "Katib"]
    FUNCTIONS = ["Lemmatizer", "Diacritizer", "POS Tagger", "Parser", "Translator", "Sentiment Analyzer", "Summarizer", "NER Extractor", "Spell Checker", "Speech Synthesizer"]
    FUNCTIONS_AR = ["مستخلص الجذور", "مشكل النصوص", "واسم أجزاء الكلام", "المحلل النحوي", "المترجم الآلي", "محلل المشاعر", "ملخص النصوص", "مستخرج الكيانات المسماة", "مصحح الأخطاء الإملائية", "مركب الكلام"]
    TECHS = ["BERT", "GPT", "T5", "Transformer", "Toolkit", "Library", "API", "Pipeline", "Engine", "Framework"]

    # 3. COURSES
    LEVELS = ["Introduction to", "Advanced", "Deep Learning for", "Practical Guide to", "Mastering", "Applied", "Foundations of", "Special Topics in", "Hands-on", "Computational Models of"]
    LEVELS_AR = ["مقدمة في", "مستوى متقدم في", "التعلم العميق لـ", "دليل عملي لـ", "إتقان", "معالجة تطبيقية لـ", "أسس", "مواضيع خاصة في", "دورة تطبيقية في", "النماذج الحاسوبية لـ"]
    TOPICS = ["Arabic Natural Language Processing", "Dialectal Arabic Models", "Arabic Speech Synthesis", "Arabic Semantic Search", "Arabic Information Extraction", "Arabizi Translation", "Sequence-to-Sequence Arabic Models", "Prompt Engineering for Arabic LLMs", "Classical Arabic Digital Humanities", "Arabic Text Summarization"]
    TOPICS_AR = ["معالجة اللغة العربية طبيعياً", "النماذج اللغوية للهجات العربية", "توليد وتوليف الكلام العربي", "البحث الدلالي باللغة العربية", "استخراج المعلومات باللغة العربية", "ترجمة نصوص العريبية", "نماذج التسلسل للتسلسل العربية", "هندسة الأوامر للنماذج اللغوية العربية", "العلوم الإنسانية الرقمية للنصوص العربية", "تلخيص النصوص العربية تلقائياً"]
    SUFFIXES = ["in Python", "for Industry", "with PyTorch", "and Computational Linguistics", "for Social Media", "in the Era of LLMs", "for Research Applications", "using Transformers", "from Scratch", "with Hands-on Projects"]
    SUFFIXES_AR = ["بلغة بايثون", "للقطاع الصناعي", "باستخدام مكتبة بايتورتش", "واللسانيات الحاسوبية", "لوسائل التواصل الاجتماعي", "في عصر النماذج اللغوية الكبيرة", "للتطبيقات البحثية", "باستخدام محولات النصوص", "من الصفر", "مع مشاريع تطبيقية"]

    # 4. NEWS
    SUBJECTS = ["Researchers at USTHB", "Consortium of Arab Universities", "Algerian AI Startup", "Google Research Team", "King Abdullah University", "Hugging Face NLP Group", "Qatar Computing Research Institute", "New York University Abu Dhabi", "Cairo University AI Lab", "American University of Beirut"]
    SUBJECTS_AR = ["باحثون من جامعة هواري بومدين", "اتحاد الجامعات العربية", "شركة جزائرية ناشئة للذكاء الاصطناعي", "فريق أبحاث جوجل", "جامعة الملك عبد الله", "مجموعة معالجة اللغة الطبيعية في هجينغ فيس", "معهد قطر لبحوث الحوسبة", "جامعة نيويورك أبوظبي", "مختبر الذكاء الاصطناعي بجامعة القاهرة", "مجموعة معالجة اللغة بجامعة بيروت الأمريكية"]
    ACTIONS = ["release a new open-source dataset for", "develop a state-of-the-art model for", "announce a workshop on", "win a prestigious award for", "launch a bilingual chatbot for", "achieve a major breakthrough in", "publish a comprehensive survey on", "open-source a high-performance library for", "partner to advance research in", "organize a coding challenge for"]
    ACTIONS_AR = ["يطلقون مجموعة بيانات جديدة مفتوحة المصدر لـ", "يطورون نموذجاً رائداً لـ", "يعلنون عن ورشة عمل حول", "يفوزون بجائزة مرموقة في مجال", "يطلقون روبوت دردشة ثنائي اللغة لـ", "يحققون إنجازاً هاماً في", "ينشرون دراسة مسحية شاملة حول", "يوفرون مكتبة برمجية عالية الأداء لـ", "يعلنون شراكة لتعزيز أبحاث", "ينظمون تحدياً برمجياً لـ"]
    DOMAINS = ["Algerian Darja speech-to-text", "Classical Arabic diacritization", "Arabizi sentiment analysis", "machine translation for Levantine dialect", "coreference resolution for medical texts", "real-time Arabic speech synthesis", "optical character recognition for historical manuscripts", "semantic search in Islamic texts", "evaluation benchmarks for Arabic LLMs", "Arabic speech-to-speech translation"]
    DOMAINS_AR = ["التعرف على الكلام بالدرجة الجزائرية", "تشكيل النصوص العربية الكلاسيكية", "تحليل مشاعر نصوص العريبية", "الترجمة الآلية للهجة الشامية", "حل الإحالات المشتركة للنصوص الطبية", "توليف الكلام العربي اللحظي", "التعرف الضوئي على حروف المخطوطات التاريخية", "البحث الدلالي في النصوص الإسلامية", "معايير تقييم النماذج اللغوية العربية", "الترجمة الفورية من الصوت إلى الصوت باللغة العربية"]

    # 5. OPPORTUNITIES
    TITLES_OP = ["NLP Research Scientist", "Senior NLP Engineer", "PhD Position in Arabic NLP", "Postdoc in Machine Translation", "Arabic Data Annotator", "Speech Recognition Engineer", "Research Intern - LLMs", "Computational Linguist", "LLM Evaluation Specialist", "AI Product Manager"]
    TITLES_OP_AR = ["باحث علمي في معالجة اللغات الطبيعية", "مهندس معالجة لغات طبيعية أول", "شاغر دكتوراه في معالجة اللغة العربية", "باحث ما بعد الدكتوراه في الترجمة الآلية", "مستشار ترميز وتصنيف بيانات عربية", "مهندس التعرف على الكلام", "متدرب أبحاث في النماذج اللغوية الكبيرة", "أخصائي لسانيات حاسوبية", "أخصائي تقييم نماذج اللغة الكبيرة", "مدير منتجات الذكاء الاصطناعي"]
    SPECIALIZATIONS = ["focusing on Algerian Darja", "for Classical Arabic Poetry", "specialized in Arabic Sentiment Analysis", "for Multilingual Speech Translation", "targeting Arabic RAG Systems", "on Cross-lingual Representation", "for Arabizi Text Normalization", "focusing on Dialogue Systems", "on Low-Resource Arabic Dialects", "for Speech-to-Text Applications"]
    SPECIALIZATIONS_AR = ["يركز على الدرجة الجزائرية", "مخصص للشعر العربي الكلاسيكي", "متخصص في تحليل المشاعر باللغة العربية", "للترجمة الكلامية متعددة اللغات", "يستهدف أنظمة التوليد المعزز بالاسترجاع العربية", "في التمثيلات اللغوية عبر اللغات", "لمعيرة ونمذجة نصوص العريبية", "يركز على الأنظمة الحوارية وتطبيقاتها", "للهجات العربية قليلة الموارد", "لتطبيقات تحويل الكلام إلى نصوص"]

    # 6. EVENTS
    ORGANIZERS = ["USTHB", "The Arab Association for AI", "The Algerian NLP Society", "IEEE Algeria Section", "QCRI Research Center", "KAUST AI Initiative", "NYUAD Computational Lab", "Cairo University", "AUB NLP Group", "Tunisian AI Association"]
    ORGANIZERS_AR = ["جامعة هواري بومدين للعلوم والتكنولوجيا", "الجمعية العربية للذكاء الاصطناعي", "الجمعية الجزائرية لمعالجة اللغة الطبيعية", "معهد مهندسي الكهرباء والإلكترونيات - فرع الجزائر", "مركز بحوث معهد قطر للحوسبة", "مبادرة الذكاء الاصطناعي بجامعة كاوست", "المختبر الحاسوبي لجامعة نيويورك أبوظبي", "جامعة القاهرة", "مجموعة معالجة اللغة بالجامعة الأمريكية في بيروت", "الجمعية التونسية للذكاء الاصطناعي"]
    EVENT_TYPES = ["International Conference on", "Symposium on", "National Workshop on", "Summer School on", "Hackathon for", "Doctoral Consortium on", "Colloquium on", "Global Summit on", "Roundtable on", "Boot Camp for"]
    EVENT_TYPES_AR = ["المؤتمر الدولي حول", "الندوة العلمية حول", "ورشة العمل الوطنية حول", "المدرسة الصيفية حول", "هاكاثون", "ملتقى الدكتوراه حول", "الحلقة الدراسية حول", "القمة العالمية لـ", "حلقة نقاشية حول", "معسكر تدريبي لـ"]
    DOMAINS_EV = ["Dialectal Arabic Machine Translation", "Arabic Large Language Models", "Social Media Mining for Arabic", "Speech Recognition in North African Dialects", "Optical Character Recognition for Arabic Manuscripts", "Semantic Web and QA in Arabic", "Arabic NLP Applications in Healthcare", "Arabizi Processing and Normalization", "Arabic NLP Benchmarking and Evaluation", "Computational Linguistics for Classical Arabic"]
    DOMAINS_EV_AR = ["الترجمة الآلية للهجات العربية الدارجة", "النماذج اللغوية الكبيرة للغة العربية", "تنقيب وسائل التواصل الاجتماعي للنصوص العربية", "التعرف على الكلام لهجات شمال إفريقيا", "التعرف الضوئي على المخطوطات العربية القديمة", "الويب الدلالي وأنظمة الإجابة عن الأسئلة", "تطبيقات معالجة اللغة الطبيعية في الرعاية الصحية", "معالجة ونمذجة نصوص العريبية", "تقييم واختبار النماذج اللغوية العربية", "اللسانيات الحاسوبية للغة العربية الكلاسيكية"]
    CITIES = ["Algiers", "Cairo", "Dubai", "Doha", "Tunis", "Beirut", "Riyadh", "Oran", "Marrakech", "Online"]
    CITIES_AR = ["الجزائر العاصمة", "القاهرة", "دبي", "الدوحة", "تونس", "بيروت", "الرياض", "وهران", "مراكش", "عبر الإنترنت"]

    # Generate 100 unique items using index combinatorics
    for i in range(10):
        for j in range(10):
            inst = INSTITUTIONS[j]
            item = {}

            if category == "corpus":
                dialect = DIALECTS[i]
                dialect_ar = DIALECTS_AR[i]
                source = SOURCES[j]
                source_ar = SOURCES_AR[j]
                task = TASKS[(i + j) % 10]
                task_ar = TASKS_AR[(i + j) % 10]
                fmt = FORMATS[(i - j) % 10]
                fmt_ar = FORMATS_AR[(i - j) % 10]

                title_en = f"{dialect} {source} for {task} ({fmt})"
                title_ar = f"{fmt_ar} {dialect_ar} المستخرجة من {source_ar} لـ {task_ar}"
                access_link = f"https://huggingface.co/datasets/arabic-nlp/{dialect.lower().replace(' ', '-')}-{source.lower().replace('/', '-').replace(' ', '-')}"

                item = {
                    "title": title_en,
                    "title_en": title_en,
                    "title_ar": title_ar,
                    "description": f"A high-quality annotated {dialect} dataset sourced from {source}, specifically formatted for {task} tasks. This {fmt.lower()} is designed to facilitate research and development in Arabic NLP, serving as a benchmarking standard.",
                    "description_en": f"A high-quality annotated {dialect} dataset sourced from {source}, specifically formatted for {task} tasks. This {fmt.lower()} is designed to facilitate research and development in Arabic NLP, serving as a benchmarking standard.",
                    "description_ar": f"مجموعة بيانات عالية الجودة ومصنفة لـ {dialect_ar} مستخرجة من {source_ar}، ومهيأة خصيصاً لمهام {task_ar}. تم تصميم هذا {fmt_ar} لتسهيل البحث والتطوير في معالجة اللغات الطبيعية.",
                    "field": "nlp",
                    "access_link": access_link,
                    "source_url": access_link,
                    "source_name": "HuggingFace Hub",
                    "keywords": f"dataset, corpus, {dialect.lower()}, {task.lower()}",
                    "confidence_score": float(85.0 + (i + j) % 15),
                    "scrape_status": "PENDING_REVIEW",
                    "approval_status": "pending",
                }

            elif category == "tools":
                name = NAMES[i]
                func = FUNCTIONS[j]
                func_ar = FUNCTIONS_AR[j]
                tech = TECHS[(i + j) % 10]
                github_url = f"https://github.com/arabic-nlp-tools/{name.lower()}-{func.lower().replace(' ', '-')}"

                title_en = f"{name}{func} - Modern Arabic {tech} Tool"
                title_ar = f"{name} لـ {func_ar} - أداة عربية معتمدة على {tech}"

                item = {
                    "title": title_en,
                    "title_en": title_en,
                    "title_ar": title_ar,
                    "description": f"An advanced computational tool designed for {func.lower()} tasks using {tech} technology. Developed for researchers and developers working on Arabic language processing, it supports both Modern Standard Arabic (MSA) and dialects.",
                    "description_en": f"An advanced computational tool designed for {func.lower()} tasks using {tech} technology. Developed for researchers and developers working on Arabic language processing, it supports both Modern Standard Arabic (MSA) and dialects.",
                    "description_ar": f"أداة حاسوبية متقدمة مصممة لمهام {func_ar} باستخدام تقنيات {tech}. تم تطويرها لدعم الباحثين والمطورين العاملين على اللغات والدرجات العربية المختلفة.",
                    "tool_type": func.lower().replace(" ", "_"),
                    "version": f"2.{i}.{j}",
                    "github_url": github_url,
                    "demo_url": f"https://demo.nlp-platform.local/{name.lower()}",
                    "documentation_link": f"https://docs.nlp-platform.local/{name.lower()}",
                    "license": "Apache-2.0" if (i % 2 == 0) else "MIT",
                    "stars_count": 150 + i * 85 + j * 12,
                    "supported_languages": "ar",
                    "source_url": github_url,
                    "source_name": "GitHub Repository",
                    "access_link": github_url,
                    "keywords": f"tool, library, {func.lower()}, {tech.lower()}",
                    "author_organization": inst["name_en"],
                    "confidence_score": float(88.0 + (i + j) % 12),
                    "scrape_status": "PENDING_REVIEW",
                    "approval_status": "pending",
                }

            elif category == "courses":
                lvl = LEVELS[i]
                lvl_ar = LEVELS_AR[i]
                top = TOPICS[j]
                top_ar = TOPICS_AR[j]
                sfx = SUFFIXES[(i + j) % 10]
                sfx_ar = SUFFIXES_AR[(i + j) % 10]

                title_en = f"{lvl} {top} ({sfx})"
                title_ar = f"{lvl_ar} {top_ar} ({sfx_ar})"
                instructor = INSTRUCTORS[i]
                enroll_url = f"{inst['website']}/courses/nlp-{i}-{j}"
                is_free = (i + j) % 2 == 0

                item = {
                    "title": title_en,
                    "title_en": title_en,
                    "title_ar": title_ar,
                    "description": f"This educational program provides a structured curriculum covering {top.lower()}. Taught by {instructor} at {inst['name_en']}, this course is highly suitable for students and practitioners who wish to master computational linguistics.",
                    "description_en": f"This educational program provides a structured curriculum covering {top.lower()}. Taught by {instructor} at {inst['name_en']}, this course is highly suitable for students and practitioners who wish to master computational linguistics.",
                    "description_ar": f"منهج تعليمي منظم يغطي {top_ar}. تقدمها الدورة تحت إشراف {instructor} في {inst['name_ar']}، وهي مناسبة تماماً للطلاب والممارسين.",
                    "field": "nlp",
                    "academic_level": "master" if (i % 2 == 0) else "bachelor",
                    "academic_year": "2025-2026",
                    "instructor": instructor,
                    "duration": f"{6 + (i + j) % 8} weeks",
                    "platform": "University eLearning" if is_free else "Coursera Partner",
                    "is_free": is_free,
                    "price": 0.0 if is_free else float(39.99 + i * 15),
                    "certificate_available": True,
                    "enrollment_url": enroll_url,
                    "source_url": enroll_url,
                    "source_name": inst["name_en"],
                    "access_link": enroll_url,
                    "institution_info": inst,
                    "confidence_score": float(90.0 + (i + j) % 10),
                    "scrape_status": "PENDING_REVIEW",
                    "approval_status": "pending",
                }

            elif category == "news":
                subj = SUBJECTS[i]
                subj_ar = SUBJECTS_AR[i]
                act = ACTIONS[j]
                act_ar = ACTIONS_AR[j]
                dom = DOMAINS[(i + j) % 10]
                dom_ar = DOMAINS_AR[(i + j) % 10]
                cats = ["paper", "news", "announcement", "blog"]
                ncat = cats[(i + j) % len(cats)]

                title_en = f"{subj} {act} {dom}"
                title_ar = f"{subj_ar} {act_ar} {dom_ar}"
                surl = f"https://arabicnlpnews.com/portal/{i:02d}-{j:02d}"

                item = {
                    "title": title_en,
                    "title_en": title_en,
                    "title_ar": title_ar,
                    "content": f"In a significant update from the AI community, {title_en}. This new development represents a major step forward for Arabic language technologies, allowing for more precise natural language processing and higher accuracy in regional dialects.",
                    "content_en": f"In a significant update from the AI community, {title_en}. This new development represents a major step forward for Arabic language technologies, allowing for more precise natural language processing and higher accuracy in regional dialects.",
                    "content_ar": f"في مستجد علمي هام من مجتمع الذكاء الاصطناعي، {title_ar}. يمثل هذا التطوير خطوة رائدة في تحسين معالجة اللهجات الإقليمية واللغة العربية الفصحى بشكل عام.",
                    "news_category": ncat,
                    "source_url": surl,
                    "source_name": "Arabic NLP News Portal",
                    "published_date": datetime.date(2026, 2, 1) + datetime.timedelta(days=(i * 8 + j)),
                    "arxiv_id": f"26{i:02d}.{j:04d}" if ncat == "paper" else "",
                    "doi": f"10.1145/nlp.{i}.{j}" if ncat == "paper" else "",
                    "confidence_score": float(92.0 + (i + j) % 8),
                    "scrape_status": "PENDING_REVIEW",
                    "approval_status": "pending",
                }

            elif category == "opportunities":
                op_title = TITLES_OP[i]
                op_title_ar = TITLES_OP_AR[i]
                spec = SPECIALIZATIONS[j]
                spec_ar = SPECIALIZATIONS_AR[j]
                op_types = ["job", "internship", "pfe", "phd", "collab"]
                op_type = op_types[(i + j) % len(op_types)]
                modes = ["remote", "hybrid", "onsite"]
                mode = modes[(i + j) % len(modes)]
                levels = ["student", "junior", "senior", "researcher"]
                level = levels[(i + j) % len(levels)]

                title_en = f"{op_title} ({spec}) at {inst['acronym']}"
                title_ar = f"{op_title_ar} ({spec_ar}) في {inst['name_ar']}"
                surl = f"{inst['website']}/careers/vacancy-{i}-{j}"
                deadline = datetime.date(2026, 12, 15) - datetime.timedelta(days=(i * 7 + j))

                item = {
                    "title": title_en,
                    "title_en": title_en,
                    "title_ar": title_ar,
                    "opportunity_type": op_type,
                    "location": "Remote" if mode == "remote" else f"{inst['city']}, {inst['acronym']}",
                    "mode": mode,
                    "level": level,
                    "description": f"We are recruiting for a {op_title} {spec} to join our research team. You will participate in implementing advanced AI and NLP models, collaborating with domain experts to build robust Arabic conversational interfaces and tools.",
                    "skills": ["python", "pytorch", "huggingface", "arabic_nlp"],
                    "contact": f"careers@{inst['domain']}",
                    "deadline": deadline,
                    "organization_en": inst["name_en"],
                    "organization_ar": inst["name_ar"],
                    "url": surl,
                    "source_url": surl,
                    "institution_info": inst,
                    "confidence_score": float(87.0 + (i + j) % 13),
                    "scrape_status": "PENDING_REVIEW",
                    "approval_status": "pending",
                }

            elif category == "events":
                org = ORGANIZERS[i]
                org_ar = ORGANIZERS_AR[i]
                etype = EVENT_TYPES[j]
                etype_ar = EVENT_TYPES_AR[j]
                dom = DOMAINS_EV[(i + j) % 10]
                dom_ar = DOMAINS_EV_AR[(i + j) % 10]
                city = CITIES[(i - j) % 10]
                city_ar = CITIES_AR[(i - j) % 10]

                title_en = f"{org} {etype} {dom} (2026 - {city})"
                title_ar = f"{org_ar}: {etype_ar} {dom_ar} (2026 - {city_ar})"

                start_date = datetime.date(2026, 10, 1) + datetime.timedelta(days=(i * 9 + j))
                end_date = start_date + datetime.timedelta(days=((i + j) % 3 + 1))
                deadline = start_date - datetime.timedelta(days=45)
                notif = start_date - datetime.timedelta(days=20)

                item = {
                    "title": title_en,
                    "title_en": title_en,
                    "title_ar": title_ar,
                    "description": f"An exclusive event organized by {org} focusing on {dom.lower()} in {city}. This event features keynote sessions, paper presentations, and hands-on tracks aimed at advancing Arabic language computing.",
                    "description_en": f"An exclusive event organized by {org} focusing on {dom.lower()} in {city}. This event features keynote sessions, paper presentations, and hands-on tracks aimed at advancing Arabic language computing.",
                    "description_ar": f"فعالية حصرية تنظمها {org_ar} تركز على {dom_ar} في {city_ar}. تشمل الفعالية جلسات رئيسية وعروضاً تقديمية للأوراق البحثية.",
                    "event_type": "conference" if "Conference" in etype else ("workshop" if "Workshop" in etype else "other"),
                    "domains": "nlp, arabic, computing, ai",
                    "start_date": start_date,
                    "end_date": end_date,
                    "contact_email": f"events@{inst['domain']}",
                    "website": f"https://events.nlp-platform.local/{i:02d}-{j:02d}",
                    "registration_link": f"https://events.nlp-platform.local/{i:02d}-{j:02d}/register",
                    "source_url": f"https://events.nlp-platform.local/{i:02d}-{j:02d}",
                    "source_name": org,
                    "is_online": city == "Online",
                    "is_hybrid": False,
                    "location": city if city == "Online" else f"{city}, {inst['acronym']}",
                    "location_en": city if city == "Online" else f"{city}, {inst['acronym']}",
                    "location_ar": city_ar if city_ar == "عبر الإنترنت" else f"{city_ar}، {inst['name_ar']}",
                    "submission_deadline": deadline,
                    "notification_date": notif,
                    "confidence_score": float(86.0 + (i + j) % 14),
                    "scrape_status": "PENDING_REVIEW",
                    "approval_status": "pending",
                    "organizer_info": inst,
                }

            items.append(item)

    return items
