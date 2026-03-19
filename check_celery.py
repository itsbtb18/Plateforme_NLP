from django_celery_beat.models import PeriodicTask
tasks = PeriodicTask.objects.filter(
    task='scraping.tasks.run_scraper_task'
)
print(f'Periodic tasks created: {tasks.count()}')
for t in tasks:
    print(f'  - {t.name}: {t.crontab} enabled={t.enabled}')
