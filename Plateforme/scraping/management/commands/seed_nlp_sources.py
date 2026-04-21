from django.core.management.base import BaseCommand

from scraping.models import ScrapingSource

SOURCES = [
    # EVENTS (22)
    {
        "name": "ACL Anthology Events",
        "url": "https://aclanthology.org",
        "category": "events",
        "scrape_config": {
            "queries": [
                "Arabic NLP conference 2025 2026",
                "ACL EMNLP NAACL workshop Arabic",
            ]
        },
    },
    {
        "name": "WikiCFP NLP",
        "url": "https://wikicfp.com/cfp/call?conference=nlp",
        "category": "events",
    },
    {
        "name": "NLP-Progress Events",
        "url": "https://nlpprogress.com",
        "category": "events",
    },
    {
        "name": "Semantic Scholar Events",
        "url": "https://www.semanticscholar.org",
        "category": "events",
        "scrape_config": {"queries": ["Arabic NLP conference call for papers 2026"]},
    },
    {
        "name": "LREC-COLING",
        "url": "https://lrec-coling-2024.org",
        "category": "events",
    },
    {"name": "EACL Conferences", "url": "https://eacl.org", "category": "events"},
    {
        "name": "WANLP Workshop",
        "url": "https://sites.google.com/view/wanlp",
        "category": "events",
    },
    {
        "name": "ArabicNLP Conference",
        "url": "https://arabicnlp2024.sigarab.org",
        "category": "events",
    },
    {"name": "SIGARAB", "url": "https://sigarab.org", "category": "events"},
    {"name": "IEEE AICCSA", "url": "https://www.aiccsa.net", "category": "events"},
    {
        "name": "EMNLP Workshops",
        "url": "https://2024.emnlp.org/program/workshops/",
        "category": "events",
    },
    {"name": "ACM SIGIR", "url": "https://sigir.org", "category": "events"},
    {
        "name": "Eventbrite NLP",
        "url": "https://www.eventbrite.com",
        "category": "events",
        "scrape_config": {
            "queries": [
                "NLP artificial intelligence conference 2026 site:eventbrite.com"
            ]
        },
    },
    {
        "name": "Meetup NLP groups",
        "url": "https://www.meetup.com",
        "category": "events",
        "scrape_config": {"queries": ["NLP machine learning meetup MENA 2026"]},
    },
    {
        "name": "Papers With Code Events",
        "url": "https://paperswithcode.com",
        "category": "events",
    },
    {"name": "MLConf", "url": "https://mlconf.com", "category": "events"},
    {"name": "AI4Good Lab", "url": "https://www.ai4goodlab.com", "category": "events"},
    {
        "name": "Global AI Events",
        "url": "https://globalai.community/events",
        "category": "events",
    },
    {"name": "ICLR", "url": "https://iclr.cc", "category": "events"},
    {"name": "NeurIPS", "url": "https://neurips.cc", "category": "events"},
    {
        "name": "ICASSP Speech",
        "url": "https://2025.ieeeicassp.org",
        "category": "events",
    },
    {
        "name": "Arabic Speech Workshop",
        "url": "https://arabicspeech.org",
        "category": "events",
    },
    # TOOLS (21)
    {
        "name": "HuggingFace Arabic NLP",
        "url": "https://huggingface.co/models?language=ar",
        "category": "tools",
    },
    {
        "name": "GitHub Arabic NLP Topic",
        "url": "https://github.com/topics/arabic-nlp",
        "category": "tools",
    },
    {
        "name": "GitHub Arabic Topic",
        "url": "https://github.com/topics/arabic",
        "category": "tools",
    },
    {
        "name": "Papers With Code Arabic",
        "url": "https://paperswithcode.com/sota",
        "category": "tools",
        "scrape_config": {"queries": ["Arabic NLP state of the art model benchmark"]},
    },
    {"name": "CAMeL Tools", "url": "https://camel-lab.com", "category": "tools"},
    {
        "name": "ArabiCA Tools",
        "url": "https://github.com/CAMeL-Lab",
        "category": "tools",
    },
    {"name": "Farasa NLP", "url": "https://farasa.qcri.org", "category": "tools"},
    {
        "name": "QCRI Arabic NLP",
        "url": "https://www.qcri.org/our-research/arabic-language-technologies",
        "category": "tools",
    },
    {
        "name": "AraVec",
        "url": "https://github.com/bakrianoo/aravec",
        "category": "tools",
    },
    {
        "name": "Mazajak Sentiment",
        "url": "https://github.com/iwan-rg/mazajak",
        "category": "tools",
    },
    {
        "name": "HuggingFace Datasets Arabic",
        "url": "https://huggingface.co/datasets?language=ar",
        "category": "tools",
    },
    {
        "name": "NLTK Arabic Resources",
        "url": "https://www.nltk.org",
        "category": "tools",
    },
    {
        "name": "Stanza Arabic",
        "url": "https://stanfordnlp.github.io/stanza/",
        "category": "tools",
    },
    {"name": "spaCy Arabic", "url": "https://spacy.io/models/ar", "category": "tools"},
    {"name": "OpenNLP", "url": "https://opennlp.apache.org", "category": "tools"},
    {
        "name": "Giza++ Aligner",
        "url": "https://github.com/moses-smt/giza-pp",
        "category": "tools",
    },
    {
        "name": "Moses SMT",
        "url": "https://github.com/moses-smt/mosesdecoder",
        "category": "tools",
    },
    {
        "name": "AraBERT Models",
        "url": "https://huggingface.co/aubmindlab",
        "category": "tools",
    },
    {
        "name": "CAMeLBERT",
        "url": "https://huggingface.co/CAMeL-Lab",
        "category": "tools",
    },
    {"name": "MARBERTv2", "url": "https://huggingface.co/UBC-NLP", "category": "tools"},
    {
        "name": "AraGPT2",
        "url": "https://huggingface.co/aubmindlab/aragpt2-base",
        "category": "tools",
    },
    # CORPUS (20)
    {
        "name": "OPUS Arabic Corpora",
        "url": "https://opus.nlpl.eu",
        "category": "corpus",
    },
    {
        "name": "LDC Arabic Datasets",
        "url": "https://www.ldc.upenn.edu/language-resources/data/by-language/arabic",
        "category": "corpus",
    },
    {"name": "ELRA Arabic", "url": "https://www.elra.info", "category": "corpus"},
    {
        "name": "OSCAR Arabic Corpus",
        "url": "https://oscar-project.org",
        "category": "corpus",
    },
    {
        "name": "Common Crawl Arabic",
        "url": "https://commoncrawl.org",
        "category": "corpus",
    },
    {
        "name": "OpenSLR Arabic Speech",
        "url": "https://www.openslr.org",
        "category": "corpus",
        "scrape_config": {"queries": ["Arabic speech corpus dataset OpenSLR"]},
    },
    {
        "name": "Mozilla Common Voice AR",
        "url": "https://commonvoice.mozilla.org/ar",
        "category": "corpus",
    },
    {
        "name": "Tashkeela Corpus",
        "url": "https://github.com/AliOsm/tashkeela-model",
        "category": "corpus",
    },
    {
        "name": "MADAR Dialect Corpus",
        "url": "https://camel.abudhabi.nyu.edu/madar/",
        "category": "corpus",
    },
    {
        "name": "Arabic Wikipedia Dump",
        "url": "https://dumps.wikimedia.org/arwiki/",
        "category": "corpus",
    },
    {
        "name": "AQMAR NER Corpus",
        "url": "https://www.cs.cmu.edu/~ark/ArabicNER/",
        "category": "corpus",
    },
    {
        "name": "KALIMAT Corpus",
        "url": "https://sourceforge.net/projects/kalimat/",
        "category": "corpus",
    },
    {
        "name": "ANERcorp",
        "url": "https://github.com/EmnamoR/Arabic-named-entity-recognition",
        "category": "corpus",
    },
    {
        "name": "SANAD Arabic News",
        "url": "https://data.mendeley.com",
        "category": "corpus",
        "scrape_config": {
            "queries": ["Arabic NLP dataset Mendeley site:data.mendeley.com"]
        },
    },
    {
        "name": "ArSentD-LEV Sentiment",
        "url": "https://github.com/sarmenta/ArSentD-LEV",
        "category": "corpus",
    },
    {
        "name": "LABR Book Reviews",
        "url": "https://github.com/mohamedadaly/LABR",
        "category": "corpus",
    },
    {
        "name": "MSA vs Dialectal Arabic",
        "url": "https://github.com/UBC-NLP",
        "category": "corpus",
    },
    {
        "name": "Zenodo Arabic NLP",
        "url": "https://zenodo.org",
        "category": "corpus",
        "scrape_config": {"queries": ["Arabic NLP dataset corpus site:zenodo.org"]},
    },
    {
        "name": "Kaggle Arabic Datasets",
        "url": "https://www.kaggle.com/datasets",
        "category": "corpus",
        "scrape_config": {"queries": ["Arabic NLP dataset site:kaggle.com"]},
    },
    {
        "name": "GitHub Arabic Datasets",
        "url": "https://github.com/topics/arabic-dataset",
        "category": "corpus",
    },
    # COURSES (20)
    {
        "name": "Coursera NLP Courses",
        "url": "https://www.coursera.org/courses?query=nlp",
        "category": "courses",
    },
    {
        "name": "edX AI Arabic",
        "url": "https://www.edx.org/learn/artificial-intelligence",
        "category": "courses",
    },
    {"name": "fast.ai", "url": "https://www.fast.ai", "category": "courses"},
    {
        "name": "DeepLearning.AI",
        "url": "https://www.deeplearning.ai/courses/",
        "category": "courses",
    },
    {
        "name": "Stanford CS224N",
        "url": "https://web.stanford.edu/class/cs224n/",
        "category": "courses",
    },
    {
        "name": "Hugging Face Course",
        "url": "https://huggingface.co/learn",
        "category": "courses",
    },
    {
        "name": "MIT OpenCourseWare NLP",
        "url": "https://ocw.mit.edu",
        "category": "courses",
        "scrape_config": {
            "queries": ["NLP natural language processing MIT OpenCourseWare"]
        },
    },
    {
        "name": "Udemy NLP Arabic",
        "url": "https://www.udemy.com",
        "category": "courses",
        "scrape_config": {
            "queries": ["NLP Arabic machine learning course site:udemy.com"]
        },
    },
    {
        "name": "Google ML Crash Course",
        "url": "https://developers.google.com/machine-learning/crash-course",
        "category": "courses",
    },
    {
        "name": "Kaggle Learn NLP",
        "url": "https://www.kaggle.com/learn",
        "category": "courses",
    },
    {
        "name": "YouTube NLP Playlists",
        "url": "https://www.youtube.com",
        "category": "courses",
        "scrape_config": {
            "queries": ["Arabic NLP tutorial deep learning 2025 site:youtube.com"]
        },
    },
    {
        "name": "KAUST AI Programs",
        "url": "https://cemse.kaust.edu.sa/ai",
        "category": "courses",
    },
    {
        "name": "MBZUAI Courses",
        "url": "https://mbzuai.ac.ae/research/",
        "category": "courses",
    },
    {
        "name": "AUC Egypt NLP",
        "url": "https://www.aucegypt.edu",
        "category": "courses",
        "scrape_config": {"queries": ["NLP Arabic machine learning course AUC Egypt"]},
    },
    {"name": "USTHB Algeria AI", "url": "https://www.usthb.dz", "category": "courses"},
    {
        "name": "LinkedIn Learning NLP",
        "url": "https://www.linkedin.com/learning/",
        "category": "courses",
        "scrape_config": {
            "queries": ["NLP natural language processing LinkedIn Learning"]
        },
    },
    {
        "name": "Udacity NLP Nanodegree",
        "url": "https://www.udacity.com/course/natural-language-processing-nanodegree--nd892",
        "category": "courses",
    },
    {
        "name": "DataCamp NLP",
        "url": "https://www.datacamp.com/courses/tech:python?topic=natural-language-processing",
        "category": "courses",
    },
    {
        "name": "ANLP Arabic NLP School",
        "url": "https://sites.google.com/view/arabic-nlp-school",
        "category": "courses",
    },
    {
        "name": "AI4Arabic Education",
        "url": "https://ai4arabic.com",
        "category": "courses",
    },
    # OPPORTUNITIES (21)
    {
        "name": "Academic Positions NLP",
        "url": "https://academicpositions.com",
        "category": "opportunities",
        "scrape_config": {"queries": ["NLP Arabic postdoc PhD position 2025 2026"]},
    },
    {
        "name": "Jobs.ac.uk NLP",
        "url": "https://www.jobs.ac.uk",
        "category": "opportunities",
        "scrape_config": {
            "queries": ["NLP Arabic language processing research position"]
        },
    },
    {
        "name": "ScholarshipDB Arabic AI",
        "url": "https://scholarshipdb.net",
        "category": "opportunities",
        "scrape_config": {
            "queries": ["NLP Arabic machine learning PhD scholarship MENA"]
        },
    },
    {
        "name": "LinkedIn NLP Jobs",
        "url": "https://www.linkedin.com/jobs/",
        "category": "opportunities",
        "scrape_config": {"queries": ["NLP engineer Arabic language MENA remote 2025"]},
    },
    {
        "name": "Indeed NLP",
        "url": "https://www.indeed.com",
        "category": "opportunities",
        "scrape_config": {
            "queries": ["NLP engineer Arabic language processing job 2025"]
        },
    },
    {
        "name": "EURAXESS Arabic AI",
        "url": "https://euraxess.ec.europa.eu/jobs",
        "category": "opportunities",
    },
    {
        "name": "KAUST Fellowships",
        "url": "https://cemse.kaust.edu.sa/academics/postdoc",
        "category": "opportunities",
    },
    {
        "name": "MBZUAI PhD Openings",
        "url": "https://mbzuai.ac.ae/study/phd-programs/",
        "category": "opportunities",
    },
    {
        "name": "QCRI Jobs",
        "url": "https://www.hbku.edu.qa/en/careers",
        "category": "opportunities",
    },
    {
        "name": "Google Research MENA",
        "url": "https://research.google/careers/",
        "category": "opportunities",
        "scrape_config": {"queries": ["Google Research NLP Arabic internship 2025"]},
    },
    {
        "name": "Microsoft Research NLP",
        "url": "https://www.microsoft.com/en-us/research/careers/",
        "category": "opportunities",
    },
    {
        "name": "Meta AI Research",
        "url": "https://ai.meta.com/careers/",
        "category": "opportunities",
    },
    {
        "name": "Amazon AWS NLP",
        "url": "https://www.amazon.jobs",
        "category": "opportunities",
        "scrape_config": {"queries": ["NLP Arabic language scientist Amazon"]},
    },
    {
        "name": "TalentEarth MENA Tech",
        "url": "https://www.bayt.com",
        "category": "opportunities",
        "scrape_config": {
            "queries": ["NLP data scientist Arabic machine learning bayt.com"]
        },
    },
    {
        "name": "Naukri Gulf NLP",
        "url": "https://www.naukrigulf.com",
        "category": "opportunities",
    },
    {
        "name": "French INRIA Postdoc",
        "url": "https://jobs.inria.fr",
        "category": "opportunities",
        "scrape_config": {"queries": ["NLP Arabic postdoc INRIA France"]},
    },
    {
        "name": "Daraj Internships",
        "url": "https://www.asuai.com",
        "category": "opportunities",
    },
    {
        "name": "Masader Opportunities",
        "url": "https://arbml.github.io/masader/",
        "category": "opportunities",
    },
    {
        "name": "AI Grants Database",
        "url": "https://aigrants.org",
        "category": "opportunities",
    },
    {
        "name": "Open Philanthropy AI",
        "url": "https://www.openphilanthropy.org/grants/",
        "category": "opportunities",
    },
    {
        "name": "Mozilla Foundation Grants",
        "url": "https://foundation.mozilla.org/en/what-we-fund/",
        "category": "opportunities",
    },
    # NEWS (22)
    {
        "name": "arXiv cs.CL Arabic",
        "url": "https://arxiv.org/list/cs.CL/recent",
        "category": "news",
    },
    {
        "name": "arXiv cs.AI",
        "url": "https://arxiv.org/list/cs.AI/recent",
        "category": "news",
    },
    {
        "name": "Semantic Scholar Arabic NLP",
        "url": "https://www.semanticscholar.org",
        "category": "news",
        "scrape_config": {"queries": ["Arabic NLP 2025 paper"]},
    },
    {
        "name": "ACL Anthology Recent",
        "url": "https://aclanthology.org/",
        "category": "news",
    },
    {
        "name": "HuggingFace Blog",
        "url": "https://huggingface.co/blog",
        "category": "news",
    },
    {"name": "Google AI Blog", "url": "https://ai.googleblog.com", "category": "news"},
    {
        "name": "DeepMind Blog",
        "url": "https://www.deepmind.com/blog",
        "category": "news",
    },
    {
        "name": "MIT Technology Review AI",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/",
        "category": "news",
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/",
        "category": "news",
    },
    {"name": "The Gradient", "url": "https://thegradient.pub", "category": "news"},
    {
        "name": "Towards Data Science NLP",
        "url": "https://towardsdatascience.com",
        "category": "news",
        "scrape_config": {
            "queries": ["Arabic NLP transformer BERT site:towardsdatascience.com"]
        },
    },
    {"name": "Distill.pub", "url": "https://distill.pub", "category": "news"},
    {
        "name": "AI News Arabic Tech",
        "url": "https://www.ai-techpark.com",
        "category": "news",
    },
    {
        "name": "Reuters Tech AI",
        "url": "https://www.reuters.com/technology/artificial-intelligence/",
        "category": "news",
    },
    {
        "name": "Arabic NLP Twitter/X",
        "url": "https://twitter.com",
        "category": "news",
        "scrape_config": {"queries": ["Arabic NLP research 2025 announcement Twitter"]},
    },
    {
        "name": "WIRED AI",
        "url": "https://www.wired.com/tag/artificial-intelligence/",
        "category": "news",
    },
    {
        "name": "AI Magazine AAAI",
        "url": "https://ojs.aaai.org/aimagazine/",
        "category": "news",
    },
    {
        "name": "Nature Machine Intelligence",
        "url": "https://www.nature.com/natmachintell/",
        "category": "news",
    },
    {
        "name": "JAIR Journal",
        "url": "https://www.jair.org/index.php/jair",
        "category": "news",
    },
    {
        "name": "Computational Linguistics Journal",
        "url": "https://direct.mit.edu/coli",
        "category": "news",
    },
    {"name": "OpenAI Blog", "url": "https://openai.com/blog", "category": "news"},
    {
        "name": "Anthropic Research",
        "url": "https://www.anthropic.com/research",
        "category": "news",
    },
]


class Command(BaseCommand):
    help = "Seed high-quality NLP-focused scraping sources."

    def handle(self, *args, **options):
        defaults_base = {
            "is_active": True,
            "is_default": True,
            "source_type": "web",
            "schedule_tier": "medium",
            "fail_count": 0,
        }

        created_count = 0
        category_set = set()

        for source in SOURCES:
            category = source["category"]
            category_set.add(category)

            defaults = dict(defaults_base)
            defaults["scrape_config"] = source.get("scrape_config", {})

            _, created = ScrapingSource.objects.get_or_create(
                name=source["name"],
                url=source["url"],
                category=category,
                defaults=defaults,
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created_count} sources across {len(category_set)} categories."
            )
        )
