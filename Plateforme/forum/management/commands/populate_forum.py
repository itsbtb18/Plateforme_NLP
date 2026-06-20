from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from forum.models import Topic, ChatRoom, Message
from datetime import datetime, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate forum with topics, chatrooms and messages in Arabic'

    def handle(self, *args, **options):
        self.stdout.write('Creating forum discussions...\n')
        
        creator = User.objects.filter(is_superuser=True).first()
        if not creator:
            self.stdout.write(self.style.WARNING('No superuser found'))
            return
        
        # Create topics
        topics_data = [
            {
                'title': 'معالجة اللغة الطبيعية',
                'description': 'مناقشات حول تقنيات ومناهج معالجة اللغة الطبيعية العربية',
                'chatrooms': [
                    {
                        'name': 'الترجمة الآلية',
                        'description': 'نقاش حول أنظمة الترجمة الآلية للغة العربية',
                        'messages': [
                            'ما هي أفضل نماذج الترجمة الآلية للغة العربية حالياً؟',
                            'أنصح باستخدام نماذج mBERT أو AraGPT المدربة على نصوص عربية كبيرة',
                            'هل جربتم Google Translate API أم تفضلون بناء نموذج خاص؟',
                            'نحن نعمل على بناء نموذج خاص باستخدام Transformers ونتائجه واعدة',
                        ]
                    },
                    {
                        'name': 'التعرف على الكيانات المسماة',
                        'description': 'استخراج الأسماء والأماكن والتواريخ من النصوص العربية',
                        'messages': [
                            'ما هي التحديات الرئيسية في NER للغة العربية؟',
                            'غياب التشكيل والتصاق الكلمات من أكبر التحديات',
                            'هل هناك مكتبات جاهزة للـ NER بالعربية؟',
                            'نعم، مثل CAMeL Tools و Stanza وهناك نماذج BERT عربية ممتازة',
                        ]
                    },
                ]
            },
            {
                'title': 'التعلم الآلي والذكاء الاصطناعي',
                'description': 'مناقشات عامة حول تقنيات التعلم الآلي المستخدمة في معالجة اللغة',
                'chatrooms': [
                    {
                        'name': 'نماذج Transformer',
                        'description': 'مناقشة حول نماذج المحولات مثل BERT و GPT',
                        'messages': [
                            'ما الفرق بين BERT و GPT في معالجة اللغة العربية؟',
                            'BERT ثنائي الاتجاه ومناسب للفهم، GPT أحادي الاتجاه ومناسب للتوليد',
                            'أيهما أفضل لتحليل المشاعر بالعربية؟',
                            'BERT عادة أفضل للتصنيف وتحليل المشاعر، خاصة AraBERT',
                        ]
                    },
                    {
                        'name': 'التدريب على بيانات عربية',
                        'description': 'كيفية جمع وتحضير البيانات لتدريب النماذج',
                        'messages': [
                            'أين يمكن إيجاد مدونات نصية عربية كبيرة؟',
                            'يمكنك استخدام Arabic Wikipedia، OSIAN corpus، أو بناء مدونة خاصة',
                            'ما هو حجم البيانات المناسب لتدريب نموذج BERT؟',
                            'على الأقل عدة ملايين من الجمل، كلما زادت البيانات كانت النتائج أفضل',
                        ]
                    },
                ]
            },
            {
                'title': 'الأدوات والمكتبات البرمجية',
                'description': 'مشاركة ومناقشة الأدوات والمكتبات المفيدة للباحثين',
                'chatrooms': [
                    {
                        'name': 'مكتبات Python للـ NLP العربي',
                        'description': 'أفضل المكتبات البرمجية لمعالجة اللغة العربية',
                        'messages': [
                            'ما هي أفضل مكتبة لمعالجة النصوص العربية في Python؟',
                            'CAMeL Tools ممتازة للتحليل الصرفي، و Farasa للتجزئة',
                            'هل NLTK تدعم العربية جيداً؟',
                            'دعمها محدود، أنصح باستخدام مكتبات متخصصة في العربية',
                        ]
                    },
                    {
                        'name': 'أدوات التوسيم والتحليل',
                        'description': 'أدوات التوسيم الصرفي والنحوي للنصوص العربية',
                        'messages': [
                            'كيف يمكن تشكيل النصوص العربية آلياً؟',
                            'يمكن استخدام مكتبة Tashkeela أو Shakkala، أو نماذج BERT مدربة',
                            'ما دقة هذه الأدوات؟',
                            'تتراوح بين 85-95% حسب جودة النموذج ونوع النص',
                        ]
                    },
                ]
            },
            {
                'title': 'البحث العلمي والنشر',
                'description': 'مناقشات حول البحث الأكاديمي والنشر في مجال NLP',
                'chatrooms': [
                    {
                        'name': 'المؤتمرات والمجلات',
                        'description': 'معلومات عن المؤتمرات والمجلات العلمية المتخصصة',
                        'messages': [
                            'ما هي أهم المؤتمرات الدولية في مجال NLP؟',
                            'ACL, EMNLP, NAACL, COLING هي الأهم عالمياً',
                            'هل هناك مؤتمرات متخصصة في اللغة العربية؟',
                            'نعم، مثل WANLP و ArabicNLP workshop في ACL',
                        ]
                    },
                    {
                        'name': 'أفكار بحثية',
                        'description': 'مشاركة ومناقشة الأفكار البحثية الجديدة',
                        'messages': [
                            'أبحث عن فكرة بحثية جديدة في مجال معالجة اللهجات العربية',
                            'يمكنك العمل على تحسين نماذج التعرف على اللهجات أو الترجمة بين اللهجات',
                            'هل هناك datasets للهجات الجزائرية؟',
                            'نعم، يمكن البحث في MADAR corpus ويحتوي على عدة لهجات عربية',
                        ]
                    },
                ]
            },
            {
                'title': 'مشاريع التخرج والأطروحات',
                'description': 'مساعدة الطلاب في مشاريع التخرج والأطروحات الجامعية',
                'chatrooms': [
                    {
                        'name': 'أفكار مشاريع ماستر',
                        'description': 'اقتراحات لمشاريع تخرج الماستر في NLP',
                        'messages': [
                            'أحتاج فكرة مشروع ماستر في معالجة اللغة العربية',
                            'يمكنك بناء chatbot عربي أو نظام تلخيص أخبار أو محلل مشاعر',
                            'ما هي الأدوات المطلوبة؟',
                            'Python، مكتبات NLP، و framework للـ web مثل Flask أو Django',
                        ]
                    },
                    {
                        'name': 'المساعدة التقنية',
                        'description': 'حل المشاكل التقنية في المشاريع',
                        'messages': [
                            'أواجه مشكلة في encoding النصوص العربية',
                            'تأكد من استخدام UTF-8 في جميع الملفات والقراءة والكتابة',
                            'كيف أحسن دقة نموذج التصنيف الخاص بي؟',
                            'جرب زيادة البيانات، تحسين المعالجة الأولية، أو استخدام نموذج مُدرب مسبقاً',
                        ]
                    },
                ]
            },
        ]
        
        created_topics = 0
        created_chatrooms = 0
        created_messages = 0
        
        for topic_data in topics_data:
            topic, created = Topic.objects.get_or_create(
                title=topic_data['title'],
                defaults={
                    'description': topic_data['description'],
                    'creator': creator,
                    'is_closed': False
                }
            )
            if created:
                created_topics += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created topic: {topic.title}'))
            
            for chatroom_data in topic_data.get('chatrooms', []):
                chatroom, created = ChatRoom.objects.get_or_create(
                    topic=topic,
                    name=chatroom_data['name'],
                    defaults={
                        'description': chatroom_data['description'],
                        'creator': creator
                    }
                )
                if created:
                    created_chatrooms += 1
                    self.stdout.write(f'  ✓ Created chatroom: {chatroom.name}')
                    
                    # Add messages
                    for idx, msg_content in enumerate(chatroom_data.get('messages', [])):
                        Message.objects.create(
                            chatroom=chatroom,
                            user=creator,
                            content=msg_content,
                            timestamp=datetime.now() - timedelta(hours=len(chatroom_data['messages']) - idx)
                        )
                        created_messages += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created {created_topics} topics'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {created_chatrooms} chatrooms'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {created_messages} messages'))
        self.stdout.write(self.style.SUCCESS(f'\nTotal topics: {Topic.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total chatrooms: {ChatRoom.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total messages: {Message.objects.count()}'))
