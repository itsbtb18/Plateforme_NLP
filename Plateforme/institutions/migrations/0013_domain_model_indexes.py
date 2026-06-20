# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('institutions', '0012_institution_affiliated_researchers_count_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='institution',
            name='website',
            field=models.URLField(blank=True, db_index=True, verbose_name='Website'),
        ),
    ]
