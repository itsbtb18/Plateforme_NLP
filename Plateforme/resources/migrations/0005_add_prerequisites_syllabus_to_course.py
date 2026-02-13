from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0004_add_uploaded_file_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='prerequisites',
            field=models.TextField(
                blank=True,
                default='',
                help_text='List the prerequisites for this course',
                verbose_name='Prerequisites',
            ),
        ),
        migrations.AddField(
            model_name='course',
            name='syllabus',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Describe the syllabus and curriculum of this course',
                verbose_name='Syllabus & Curriculum',
            ),
        ),
    ]
