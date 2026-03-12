from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0004_securitylog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='securitylog',
            name='action',
            field=models.CharField(
                choices=[
                    ('login', 'Login'),
                    ('failed_login', 'Failed Login'),
                    ('upload', 'Upload'),
                    ('blocked_upload', 'Blocked Upload'),
                    ('create', 'Create'),
                    ('update', 'Update'),
                    ('delete', 'Delete'),
                    ('other', 'Other'),
                ],
                default='other',
                max_length=32,
            ),
        ),
    ]
