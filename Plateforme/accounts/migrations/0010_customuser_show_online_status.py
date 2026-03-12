from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_friendship'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='show_online_status',
            field=models.BooleanField(default=True, verbose_name='show online status'),
        ),
    ]
