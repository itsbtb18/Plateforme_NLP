from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0003_blockedupload'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SecurityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(blank=True, default='member', max_length=32)),
                ('action', models.CharField(choices=[('login', 'Login'), ('upload', 'Upload'), ('blocked_upload', 'Blocked Upload'), ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('other', 'Other')], default='other', max_length=32)),
                ('method', models.CharField(blank=True, default='GET', max_length=10)),
                ('ip_address', models.CharField(blank=True, default='', max_length=64)),
                ('path', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Security Log',
                'verbose_name_plural': 'Security Logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='securitylog',
            index=models.Index(fields=['created_at'], name='pages_secur_created_0d0706_idx'),
        ),
        migrations.AddIndex(
            model_name='securitylog',
            index=models.Index(fields=['action', 'created_at'], name='pages_secur_action__95e6f4_idx'),
        ),
        migrations.AddIndex(
            model_name='securitylog',
            index=models.Index(fields=['role', 'created_at'], name='pages_secur_role_43e7d0_idx'),
        ),
    ]
