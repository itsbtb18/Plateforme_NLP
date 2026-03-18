# Generated migration for GlobalSettings model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GlobalSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_name', models.CharField(default='NLP Platform', help_text='Name of the platform', max_length=255)),
                ('site_description', models.TextField(blank=True, help_text='Description of the platform')),
                ('site_url', models.URLField(default='http://localhost:8000', help_text='Main URL of the platform')),
                ('logo', models.ImageField(blank=True, help_text='Platform logo', null=True, upload_to='logos/')),
                ('favicon', models.ImageField(blank=True, help_text='Platform favicon', null=True, upload_to='favicons/')),
                ('email_from_name', models.CharField(default='NLP Platform', help_text='Name to display in "From" field of emails', max_length=255)),
                ('email_from_address', models.EmailField(default='noreply@nlpplatform.com', help_text='Email address to send from', max_length=254)),
                ('smtp_host', models.CharField(default='smtp.gmail.com', help_text='SMTP server host', max_length=255)),
                ('smtp_port', models.IntegerField(default=587, help_text='SMTP server port')),
                ('smtp_use_tls', models.BooleanField(default=True, help_text='Use TLS for SMTP connection')),
                ('admin_email', models.EmailField(default='admin@nlpplatform.com', help_text='Email address to send admin notifications to', max_length=254)),
                ('enable_email_notifications', models.BooleanField(default=True, help_text='Enable email notifications')),
                ('notify_on_user_registration', models.BooleanField(default=True, help_text='Send notification when new user registers')),
                ('notify_on_resource_submission', models.BooleanField(default=True, help_text='Send notification when new resource is submitted')),
                ('notify_on_forum_post', models.BooleanField(default=True, help_text='Send notification on new forum posts')),
                ('notify_on_event', models.BooleanField(default=True, help_text='Send notification for new events')),
                ('notification_email', models.EmailField(default='notifications@nlpplatform.com', help_text='Email to send notification alerts to', max_length=254)),
                ('enable_user_registration', models.BooleanField(default=True, help_text='Allow new user registrations')),
                ('enable_social_login', models.BooleanField(default=True, help_text='Enable social login (Google, etc.)')),
                ('enable_two_factor_auth', models.BooleanField(default=True, help_text='Enable two-factor authentication')),
                ('enable_forum', models.BooleanField(default=True, help_text='Enable forum functionality')),
                ('enable_qa', models.BooleanField(default=True, help_text='Enable Q&A functionality')),
                ('enable_events', models.BooleanField(default=True, help_text='Enable events functionality')),
                ('enable_projects', models.BooleanField(default=True, help_text='Enable projects functionality')),
                ('enable_chatbot', models.BooleanField(default=True, help_text='Enable chatbot functionality')),
                ('enable_resource_submission', models.BooleanField(default=True, help_text='Allow users to submit resources')),
                ('enable_resource_approval', models.BooleanField(default=True, help_text='Require approval for submitted resources')),
                ('enable_content_moderation', models.BooleanField(default=True, help_text='Enable content moderation features')),
                ('max_upload_size_mb', models.IntegerField(default=50, help_text='Maximum file upload size in MB')),
                ('require_email_verification', models.BooleanField(default=True, help_text='Require email verification for registration')),
                ('maintenance_mode', models.BooleanField(default=False, help_text='Enable maintenance mode (site unavailable to public)')),
                ('maintenance_message', models.TextField(blank=True, help_text='Message to display during maintenance')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='settings_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Global Settings',
                'verbose_name_plural': 'Global Settings',
            },
        ),
    ]
