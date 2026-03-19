import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
try:
    django.setup()
except Exception:
    traceback.print_exc()
    exit(1)

try:
    from django_celery_beat.models import PeriodicTask
    tasks = PeriodicTask.objects.filter(
        task='scraping.tasks.run_scraper_task'
    )
    print(f'Periodic tasks: {tasks.count()}')
    for t in tasks:
        print(f'  {t.name}: enabled={t.enabled}')
except Exception:
    traceback.print_exc()
    exit(1)
