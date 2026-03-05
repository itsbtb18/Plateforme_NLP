from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0002_adminactivitylog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BlockedUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(blank=True, default='', max_length=255)),
                ('reason', models.CharField(blank=True, default='', max_length=255)),
                ('path', models.CharField(blank=True, default='', max_length=255)),
                ('ip_address', models.CharField(blank=True, default='', max_length=64)),
                ('blocked_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='blocked_uploads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Blocked upload',
                'verbose_name_plural': 'Blocked uploads',
                'ordering': ['-blocked_at'],
            },
        ),
        migrations.AddIndex(
            model_name='blockedupload',
            index=models.Index(fields=['blocked_at'], name='pages_blocke_blocked_5e25c3_idx'),
        ),
        migrations.AddIndex(
            model_name='blockedupload',
            index=models.Index(fields=['ip_address', 'blocked_at'], name='pages_blocke_ip_addr_957baa_idx'),
        ),
    ]
