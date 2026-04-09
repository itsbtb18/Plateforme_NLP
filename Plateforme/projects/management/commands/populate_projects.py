
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from projects.models import Project, ProjectMember
from institutions.models import Institution
from datetime import datetime, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate projects with sample data in Arabic'

    def handle(self, *args, **options):
        self.stdout.write('Creating projects...\n')
        
        # Get superuser as coordinator
        coordinator = User.objects.filter(is_superuser=True).first()
        if not coordinator:
            self.stdout.write(self.style.WARNING('No superuser found to assign as coordinator'))
            return
        
        # Get institutions
        institutions = {
            'CERIST': Institution.objects.filter(acronym='CERIST').first(),
            'USTHB': Institution.objects.filter(acronym='USTHB').first(),
            'ESI': Institution.objects.filter(acronym='ESI').first(),
            'CDTA': Institution.objects.filter(acronym='CDTA').first(),
            'CRTI': Institution.objects.filter(acronym='CRTI').first(),
            'UNIV-ALG1': Institution.objects.filter(acronym='UNIV-ALG1').first(),
            'UAMB': Institution.objects.filter(acronym='UAMB').first(),
            'CRNA': Institution.objects.filter(acronym='CRNA').first(),
        }
        
        today = datetime.now().date()
        
        # Sample projects data
        projects_data = [
            {
                'title': 'نظام الترجمة الآلية العصبية للغة العربية',
                'institution': institutions['CDTA'],
                'status': 'ongoing',
                'description': '''مشروع بحثي يهدف إلى تطوير نظام ترجمة آلية عصبية متقدم للغة العربية باستخدام تقنيات التعلم العميق والمحولات (Transformers).

الأهداف الرئيسية:
- تطوير نموذج ترجمة عربي-إنجليزي وإنجليزي-عربي
- دعم اللهجات العربية المختلفة
- تحسين جودة الترجمة بنسبة 20% عن النماذج الحالية
- إنشاء قاعدة بيانات ثنائية اللغة كبيرة

التقنيات المستخدمة: PyTorch, Transformers, BERT, مكتبات معالجة اللغة الطبيعية''',
                'date_start': today - timedelta(days=180),
                'date_end': today + timedelta(days=185),
            },
            {
                'title': 'منصة تحليل المشاعر في وسائل التواصل الاجتماعي العربية',
                'institution': institutions['ESI'],
                'status': 'ongoing',
                'description': '''مشروع يهدف إلى بناء منصة متكاملة لتحليل المشاعر والآراء في النصوص العربية على وسائل التواصل الاجتماعي.

المميزات:
- تحليل المشاعر (إيجابي، سلبي، محايد)
- كشف الموضوعات الشائعة
- تحليل الاتجاهات الزمنية
- دعم اللهجة الجزائرية والدارجة

التطبيقات: مراقبة العلامات التجارية، تحليل الرأي العام، البحث الاجتماعي''',
                'date_start': today - timedelta(days=120),
                'date_end': today + timedelta(days=245),
            },
            {
                'title': 'المدونة الوطنية للنصوص العربية المشكولة',
                'institution': institutions['CERIST'],
                'status': 'ongoing',
                'description': '''مشروع وطني طموح لبناء أكبر مدونة لغوية للنصوص العربية المشكولة والمعالجة لغوياً.

الأهداف:
- جمع 100 مليون كلمة من النصوص العربية
- تشكيل النصوص آلياً وتصحيحها يدوياً
- التوسيم الصرفي والنحوي الكامل
- إتاحة المدونة مجاناً للباحثين

المصادر: كتب، صحف، مواقع إخبارية، محتوى أكاديمي، نصوص تاريخية''',
                'date_start': today - timedelta(days=365),
                'date_end': today + timedelta(days=365),
            },
            {
                'title': 'نظام التعرف الآلي على الكلام العربي',
                'institution': institutions['CRTI'],
                'status': 'ongoing',
                'description': '''تطوير نظام متقدم للتعرف الآلي على الكلام العربي الفصحى واللهجات المحلية.

المكونات:
- نماذج صوتية عميقة (Deep Neural Networks)
- نماذج لغوية احتمالية
- معالجة الضوضاء والتحسين الصوتي
- دعم اللهجة الجزائرية

الاستخدامات: الإملاء الصوتي، التحكم الصوتي، ترجمة الخطابات، خدمات الزبائن الآلية''',
                'date_start': today - timedelta(days=210),
                'date_end': today + timedelta(days=155),
            },
            {
                'title': 'مساعد حواري ذكي للإجابة عن الأسئلة بالعربية',
                'institution': institutions['USTHB'],
                'status': 'ongoing',
                'description': '''بناء نظام chatbot متقدم قادر على فهم الأسئلة بالعربية وتقديم إجابات دقيقة من مصادر موثوقة.

التقنيات:
- معالجة اللغة الطبيعية (NLP)
- نماذج الفهم العميق (BERT Arabic)
- استرجاع المعلومات (Information Retrieval)
- توليد الإجابات (Answer Generation)

مجالات التطبيق: التعليم، الخدمات الحكومية، المساعدة القانونية، الاستشارات الطبية''',
                'date_start': today - timedelta(days=150),
                'date_end': today + timedelta(days=215),
            },
            {
                'title': 'أداة تلخيص النصوص العربية الآلي',
                'institution': institutions['UNIV-ALG1'],
                'status': 'ongoing',
                'description': '''تطوير أداة متقدمة لتلخيص النصوص العربية الطويلة بشكل آلي مع الحفاظ على المعنى الأساسي.

الأنواع:
- التلخيص الاستخراجي (Extractive)
- التلخيص التجريدي (Abstractive)
- التلخيص متعدد الوثائق

المميزات: سرعة عالية، دقة ممتازة، دعم تنسيقات متعددة (PDF, Word, HTML)

الاستخدامات: تلخيص الأخبار، البحوث الأكاديمية، التقارير، الوثائق القانونية''',
                'date_start': today - timedelta(days=90),
                'date_end': today + timedelta(days=275),
            },
            {
                'title': 'نظام استخراج المعلومات من النصوص العربية',
                'institution': institutions['CERIST'],
                'status': 'planned',
                'description': '''مشروع لبناء نظام متقدم لاستخراج المعلومات المهيكلة من النصوص العربية غير المهيكلة.

القدرات:
- التعرف على الكيانات المسماة (NER)
- استخراج العلاقات بين الكيانات
- استخراج الأحداث
- بناء قواعد معرفية

التطبيقات: تحليل الأخبار، البحث القانوني، الذكاء الاقتصادي، الأرشفة الرقمية''',
                'date_start': today + timedelta(days=30),
                'date_end': today + timedelta(days=395),
            },
            {
                'title': 'محرك بحث دلالي للمحتوى العربي',
                'institution': institutions['CDTA'],
                'status': 'planned',
                'description': '''تطوير محرك بحث متقدم يعتمد على الفهم الدلالي للغة العربية وليس فقط المطابقة اللفظية.

التقنيات:
- نماذج التمثيل الدلالي (Semantic Embeddings)
- البحث العصبي (Neural Search)
- فهم استعلامات اللغة الطبيعية
- الترتيب الذكي للنتائج

المميزات: فهم المترادفات، البحث بالمعنى، دعم الأسئلة الطبيعية، نتائج أكثر دقة''',
                'date_start': today + timedelta(days=60),
                'date_end': today + timedelta(days=425),
            },
            {
                'title': 'نظام التصحيح الإملائي والنحوي الذكي للعربية',
                'institution': institutions['ESI'],
                'status': 'completed',
                'description': '''نظام متكامل للتصحيح الإملائي والنحوي للنصوص العربية باستخدام الذكاء الاصطناعي.

الإمكانيات:
- كشف الأخطاء الإملائية والنحوية
- اقتراح التصحيحات المناسبة
- التحقق من التشكيل
- كشف الأخطاء السياقية

تم إطلاق النظام كإضافة للمتصفحات وكـ API للمطورين. يستخدمه حالياً أكثر من 50,000 مستخدم.''',
                'date_start': today - timedelta(days=540),
                'date_end': today - timedelta(days=90),
            },
            {
                'title': 'مشروع توليد النصوص العربية بالذكاء الاصطناعي',
                'institution': institutions['UAMB'],
                'status': 'ongoing',
                'description': '''بحث وتطوير نماذج توليد النصوص العربية باستخدام تقنيات التعلم العميق الحديثة.

الأهداف:
- توليد نصوص عربية متماسكة وطبيعية
- توليد المحتوى الإبداعي (شعر، قصص)
- إكمال النصوص تلقائياً
- إعادة صياغة المحتوى

التقنيات: GPT, BERT, Transformers, Fine-tuning على نصوص عربية ضخمة''',
                'date_start': today - timedelta(days=75),
                'date_end': today + timedelta(days=290),
            },
            {
                'title': 'قاموس حاسوبي شامل للغة العربية',
                'institution': institutions['CRNA'],
                'status': 'ongoing',
                'description': '''بناء قاموس حاسوبي شامل ومفتوح المصدر للغة العربية يخدم تطبيقات معالجة اللغة الطبيعية.

المحتويات:
- 200,000+ كلمة ومصطلح
- المعاني والتعريفات
- الجذور والأوزان
- المترادفات والأضداد
- أمثلة الاستخدام
- البيانات الصرفية والنحوية

الإتاحة: API مجاني، قاعدة بيانات قابلة للتحميل، توثيق كامل''',
                'date_start': today - timedelta(days=200),
                'date_end': today + timedelta(days=165),
            },
        ]
        
        created_count = 0
        for project_data in projects_data:
            if project_data['institution'] is None:
                continue
                
            # Check if project already exists
            if not Project.objects.filter(
                title=project_data['title'],
                institution=project_data['institution']
            ).exists():
                Project.objects.create(
                    title=project_data['title'],
                    description=project_data['description'],
                    institution=project_data['institution'],
                    status=project_data['status'],
                    coordinator=coordinator,
                    date_start=project_data['date_start'],
                    date_end=project_data['date_end']
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {project_data["title"][:50]}...'))
            else:
                self.stdout.write(f'⟳ Exists: {project_data["title"][:50]}...')
        
        total = Project.objects.count()
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created {created_count} new projects'))
        self.stdout.write(self.style.SUCCESS(f'Total projects: {total}'))
