from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from QA.models import Post
from django.utils.text import slugify

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate news posts in Arabic'

    def handle(self, *args, **options):
        self.stdout.write('Creating news posts...\n')
        
        author = User.objects.filter(is_superuser=True).first()
        if not author:
            self.stdout.write(self.style.WARNING('No superuser found'))
            return
        
        news_data = [
            {
                'content': '''🎉 إطلاق النسخة الجديدة من منصة معالجة اللغة العربية

نحن سعداء بالإعلان عن إطلاق النسخة المحدثة من منصتنا الوطنية للبحث في معالجة اللغة العربية الطبيعية. تتضمن النسخة الجديدة:

✨ واجهة مستخدم محسنة وسهلة الاستخدام
📚 مكتبة موسعة من الموارد والأدوات البحثية
🤝 نظام تعاوني متطور للباحثين
🎓 دورات تدريبية متخصصة في مجال NLP

انضم إلينا اليوم وكن جزءاً من مجتمع الباحثين في معالجة اللغة العربية!

#NLP #ArabicNLP #الذكاء_الاصطناعي''',
                'slug': 'new-platform-launch-2025',
            },
            {
                'content': '''📢 نتائج هاكاثون معالجة اللغة العربية 2024

تم الإعلان عن الفائزين في هاكاثون معالجة اللغة العربية لعام 2024. شارك في الفعالية أكثر من 150 مشاركاً من مختلف الجامعات الجزائرية.

🥇 المركز الأول: فريق USTHB - مشروع نظام الترجمة الآلية العصبية
🥈 المركز الثاني: فريق ESI - أداة تحليل المشاعر في وسائل التواصل الاجتماعي
🥉 المركز الثالث: فريق Univ Alger 1 - تطبيق التعرف على الكلام العربي

تهانينا لجميع الفائزين والمشاركين!

#Hackathon #AI #ArabicTech''',
                'slug': 'hackathon-results-2024',
            },
            {
                'content': '''🚀 إطلاق مشروع المدونة العربية الوطنية للنصوص

يسرنا الإعلان عن إطلاق مشروع بناء مدونة وطنية للنصوص العربية بالتعاون مع CERIST وعدة جامعات وطنية.

المشروع يهدف إلى:
📝 جمع وتصنيف ملايين النصوص العربية
🏷️ توسيم وتحليل البيانات اللغوية
🔓 إتاحة المدونة مجاناً للباحثين
📊 دعم البحث العلمي في معالجة اللغة العربية

للمشاركة في المشروع: corpus@cerist.dz

#Corpus #NLP #OpenData''',
                'slug': 'national-arabic-corpus-project',
            },
            {
                'content': '''🎓 افتتاح التسجيل في الدورة التدريبية: التعلم العميق لمعالجة اللغة العربية

تعلن جامعة USTHB عن فتح التسجيل في دورة تدريبية مكثفة حول:

📌 مدة الدورة: 6 أسابيع
📌 المستوى: متوسط إلى متقدم
📌 المحاور:
  - الشبكات العصبية المتكررة (RNN/LSTM)
  - المحولات (Transformers)
  - نماذج BERT للغة العربية
  - التطبيقات العملية

التسجيل مفتوح حتى: 15 ديسمبر 2025
للتسجيل: training@usthb.dz

#DeepLearning #Training #NLP''',
                'slug': 'deep-learning-nlp-course',
            },
            {
                'content': '''🔬 نشر ورقة بحثية جديدة في مجلة ACL عن الترجمة الآلية العربية

تهانينا لفريق البحث من CDTA على نشر ورقتهم البحثية في مجلة ACL المرموقة!

عنوان البحث: "Improving Arabic-English Neural Machine Translation using Dialectal Data Augmentation"

البحث يقدم نموذجاً جديداً يحسن جودة الترجمة الآلية بنسبة 15% مقارنة بالنماذج الحالية.

للاطلاع على البحث الكامل: https://www.cdta.dz

#Research #NMT #ACL #ArabicNLP''',
                'slug': 'acl-paper-publication',
            },
            {
                'content': '''💡 ورشة عمل مجانية: بناء chatbot بالعربية باستخدام Python

تنظم ESI ورشة عمل مجانية للمهتمين ببناء روبوتات المحادثة باللغة العربية.

📅 التاريخ: 20 ديسمبر 2025
⏰ الوقت: 14:00 - 17:00
📍 المكان: المدرسة الوطنية العليا للإعلام الآلي
💻 متطلبات: معرفة أساسية بـ Python

المواضيع المشمولة:
- معالجة النصوص العربية
- استخدام مكتبات NLP
- بناء نموذج الحوار
- تدريب ونشر الروبوت

التسجيل محدود! سجل الآن: workshop@esi.dz

#Chatbot #Python #Workshop''',
                'slug': 'chatbot-workshop-esi',
            },
            {
                'content': '''📊 تقرير: حالة معالجة اللغة العربية الطبيعية في الجزائر 2025

نشر CERIST تقريراً شاملاً عن حالة البحث والتطوير في مجال معالجة اللغة العربية في الجزائر.

أبرز النقاط:
📈 زيادة 40% في الأبحاث المنشورة مقارنة بعام 2024
👥 أكثر من 200 باحث نشط في المجال
🏆 3 جوائز دولية للباحثين الجزائريين
🎯 20+ مشروع بحثي نشط

حمل التقرير الكامل من: https://www.cerist.dz/report2025

#Report #Statistics #ArabicNLP''',
                'slug': 'nlp-state-report-2025',
            },
            {
                'content': '''🌟 تكريم الباحثين المتميزين في معالجة اللغة العربية

في حفل أقيم بجامعة الجزائر 1، تم تكريم عدد من الباحثين المتميزين في مجال معالجة اللغة العربية:

🏅 جائزة أفضل بحث: د. أحمد بن محمد - USTHB
🏅 جائزة الابتكار: د. فاطمة الزهراء - ESI
🏅 جائزة أفضل تطبيق: فريق البحث - CERIST

مبروك للجميع وإلى مزيد من النجاحات!

#Awards #Recognition #Excellence''',
                'slug': 'researchers-awards-ceremony',
            },
        ]
        
        created_count = 0
        for news in news_data:
            if not Post.objects.filter(slug=news['slug']).exists():
                Post.objects.create(
                    author=author,
                    content=news['content'],
                    slug=news['slug']
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created news: {news["slug"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'⟳ Exists: {news["slug"]}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created {created_count} news posts'))
        self.stdout.write(self.style.SUCCESS(f'Total posts: {Post.objects.count()}'))
