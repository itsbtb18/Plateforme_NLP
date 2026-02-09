from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from events.models import Event
from institutions.models import Institution
from datetime import date, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate more events in Arabic'

    def handle(self, *args, **options):
        self.stdout.write('Creating additional events...\n')
        
        author = User.objects.filter(is_superuser=True).first()
        if not author:
            self.stdout.write(self.style.WARNING('No superuser found'))
            return
        
        # Get institutions
        institutions = {
            'CERIST': Institution.objects.filter(acronym='CERIST').first(),
            'USTHB': Institution.objects.filter(acronym='USTHB').first(),
            'ESI': Institution.objects.filter(acronym='ESI').first(),
            'CDTA': Institution.objects.filter(acronym='CDTA').first(),
            'UNIV-ALG1': Institution.objects.filter(acronym='UNIV-ALG1').first(),
            'UAMB': Institution.objects.filter(acronym='UAMB').first(),
        }
        
        today = date.today()
        
        events_data = [
            {
                'title': 'هاكاثون معالجة اللغة العربية 2025',
                'description': 'هاكاثون وطني للطلاب والباحثين في مجال معالجة اللغة العربية، مع جوائز قيمة للفائزين.',
                'event_type': 'hackathon',
                'domains': 'nlp,ai,arabic_lang',
                'location': 'المدرسة الوطنية العليا للإعلام الآلي',
                'start_date': today + timedelta(days=45),
                'end_date': today + timedelta(days=47),
                'submission_deadline': today + timedelta(days=20),
                'website': 'https://www.esi.dz',
                'organizer': institutions['ESI'],
                'contact_email': 'hackathon@esi.dz',
                'is_approved': True,
            },
            {
                'title': 'دعوة لتقديم الأوراق البحثية - مجلة معالجة اللغة العربية',
                'description': 'دعوة لتقديم الأوراق البحثية للنشر في العدد الخاص حول تقنيات التعلم العميق في معالجة اللغة العربية.',
                'event_type': 'call_for_papers',
                'domains': 'nlp,machine_learning,ai',
                'location': '',
                'start_date': today + timedelta(days=90),
                'end_date': today + timedelta(days=180),
                'submission_deadline': today + timedelta(days=75),
                'website': 'https://www.cerist.dz',
                'organizer': institutions['CERIST'],
                'contact_email': 'journal@cerist.dz',
                'is_approved': True,
            },
            {
                'title': 'ورشة عمل تحليل المشاعر في النصوص العربية',
                'description': 'ورشة عمل متخصصة في تقنيات تحليل المشاعر والآراء من النصوص العربية على وسائل التواصل الاجتماعي.',
                'event_type': 'workshop',
                'domains': 'sentiment_analysis,nlp,text_mining',
                'location': 'جامعة عبد الرحمان ميرة - بجاية',
                'start_date': today + timedelta(days=25),
                'end_date': today + timedelta(days=26),
                'website': 'https://www.univ-bejaia.dz',
                'organizer': institutions['UAMB'],
                'contact_email': 'workshop@univ-bejaia.dz',
                'is_approved': True,
            },
            {
                'title': 'المؤتمر الوطني للذكاء الاصطناعي وتطبيقاته',
                'description': 'مؤتمر وطني يجمع الباحثين والمطورين في مجال الذكاء الاصطناعي لمناقشة أحدث التطورات والتطبيقات.',
                'event_type': 'conference',
                'domains': 'ai,machine_learning,nlp',
                'location': 'الجزائر العاصمة - USTHB',
                'start_date': today + timedelta(days=120),
                'end_date': today + timedelta(days=123),
                'submission_deadline': today + timedelta(days=90),
                'website': 'https://www.usthb.dz',
                'organizer': institutions['USTHB'],
                'contact_email': 'ai-conference@usthb.dz',
                'is_approved': True,
            },
            {
                'title': 'ندوة التعرف الآلي على الكلام العربي',
                'description': 'ندوة علمية حول تقنيات التعرف الآلي على الكلام العربي والتحديات المرتبطة بها.',
                'event_type': 'seminar',
                'domains': 'speech,nlp,ai',
                'location': '',
                'start_date': today + timedelta(days=35),
                'end_date': today + timedelta(days=35),
                'website': 'https://www.cdta.dz',
                'organizer': institutions['CDTA'],
                'contact_email': 'seminar@cdta.dz',
                'is_approved': True,
            },
            {
                'title': 'ورشة الترجمة الآلية العصبية',
                'description': 'ورشة تدريبية حول بناء أنظمة الترجمة الآلية باستخدام الشبكات العصبية العميقة.',
                'event_type': 'workshop',
                'domains': 'machine_translation,nlp,ai',
                'location': 'جامعة الجزائر 1',
                'start_date': today + timedelta(days=50),
                'end_date': today + timedelta(days=52),
                'website': 'https://www.univ-alger.dz',
                'organizer': institutions['UNIV-ALG1'],
                'contact_email': 'nmt@univ-alger.dz',
                'is_approved': True,
            },
            {
                'title': 'مؤتمر اللسانيات الحاسوبية للغة العربية',
                'description': 'مؤتمر دولي متخصص في اللسانيات الحاسوبية وتطبيقاتها على اللغة العربية.',
                'event_type': 'conference',
                'domains': 'linguistics,nlp,arabic_lang',
                'location': 'الجزائر العاصمة',
                'start_date': today + timedelta(days=150),
                'end_date': today + timedelta(days=153),
                'submission_deadline': today + timedelta(days=120),
                'website': 'https://www.cerist.dz',
                'organizer': institutions['CERIST'],
                'contact_email': 'linguistics@cerist.dz',
                'is_approved': True,
            },
            {
                'title': 'ندوة تلخيص النصوص العربية التلقائي',
                'description': 'ندوة حول تقنيات التلخيص التلقائي للنصوص العربية باستخدام الذكاء الاصطناعي.',
                'event_type': 'seminar',
                'domains': 'text_summarization,nlp,ai',
                'location': '',
                'start_date': today + timedelta(days=40),
                'end_date': today + timedelta(days=40),
                'website': 'https://www.usthb.dz',
                'organizer': institutions['USTHB'],
                'contact_email': 'summarization@usthb.dz',
                'is_approved': True,
            },
        ]
        
        created_count = 0
        for evt_data in events_data:
            if evt_data['organizer'] is None:
                continue
                
            if not Event.objects.filter(title=evt_data['title']).exists():
                Event.objects.create(created_by=author, **evt_data)
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {evt_data["title"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'⟳ Exists: {evt_data["title"]}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created {created_count} new events'))
        self.stdout.write(self.style.SUCCESS(f'Total events: {Event.objects.count()}'))
