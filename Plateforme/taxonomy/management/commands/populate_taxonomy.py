from django.core.management.base import BaseCommand
from django.utils.text import slugify

from taxonomy.models import Dataset, NLPMethod, ResearchDomain


TOP_LEVEL_DOMAINS = [
    ("Machine Translation", "الترجمة الآلية"),
    ("Named Entity Recognition", "التعرّف على الكيانات المُسماة"),
    ("Text Classification", "تصنيف النصوص"),
    ("Speech Recognition", "التعرّف على الكلام"),
    ("Sentiment Analysis", "تحليل المشاعر"),
    ("Question Answering", "الإجابة عن الأسئلة"),
    ("Summarization", "التلخيص"),
    ("Parsing", "التحليل النحوي"),
    ("Morphological Analysis", "التحليل الصرفي"),
    ("Dialect Processing", "معالجة اللهجات"),
]

METHODS = [
    ("Transformer", "المحوّل"),
    ("BERT/AraBERT", "بيرت/عربيرت"),
    ("RAG", "الاسترجاع المعزّز بالتوليد"),
    ("CRF", "حقول عشوائية شرطية"),
    ("LSTM", "ذاكرة قصيرة وطويلة المدى"),
    ("CNN", "الشبكات العصبية الالتفافية"),
    ("GPT", "المحوّل التوليدي المدرب مسبقاً"),
    ("Seq2Seq", "تسلسل إلى تسلسل"),
    ("Attention Mechanism", "آلية الانتباه"),
]

DATASETS = [
    {
        "name": "CoNLL-2003",
        "huggingface_id": "conll2003",
        "paperswithcode_id": "conll-2003",
        "language": "ar",
        "description_en": "Named entity recognition benchmark dataset.",
        "description_ar": "مجموعة مرجعية للتعرّف على الكيانات المُسماة.",
    },
    {
        "name": "OSCAR Arabic",
        "huggingface_id": "oscar",
        "paperswithcode_id": "",
        "language": "ar",
        "description_en": "Large-scale multilingual web corpus with Arabic subset.",
        "description_ar": "مستودع ويب متعدد اللغات واسع النطاق يتضمن جزءاً عربياً.",
    },
    {
        "name": "AraBench Sentiment",
        "huggingface_id": "",
        "paperswithcode_id": "",
        "language": "ar",
        "description_en": "Arabic sentiment analysis sample dataset.",
        "description_ar": "مجموعة عيّنة لتحليل المشاعر باللغة العربية.",
    },
]


class Command(BaseCommand):
    help = "Seed taxonomy data (research domains, NLP methods, datasets)."

    def handle(self, *args, **options):
        created_domains = 0
        created_methods = 0
        created_datasets = 0

        for name_en, name_ar in TOP_LEVEL_DOMAINS:
            slug = slugify(name_en)
            _, created = ResearchDomain.objects.get_or_create(
                slug=slug,
                defaults={
                    "name_en": name_en,
                    "name_ar": name_ar,
                    "parent": None,
                },
            )
            created_domains += int(created)

        for name_en, name_ar in METHODS:
            slug = slugify(name_en)
            _, created = NLPMethod.objects.get_or_create(
                slug=slug,
                defaults={
                    "name_en": name_en,
                    "name_ar": name_ar,
                },
            )
            created_methods += int(created)

        for item in DATASETS:
            _, created = Dataset.objects.get_or_create(
                name=item["name"],
                defaults=item,
            )
            created_datasets += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Taxonomy populated. "
                f"Domains created: {created_domains}, "
                f"Methods created: {created_methods}, "
                f"Datasets created: {created_datasets}"
            )
        )

