"""
Migration pour restaurer le champ name à partir de name_en
"""
from django.db import migrations, models


def copy_name_en_to_name(apps, schema_editor):
    """Copier name_en vers name"""
    Institution = apps.get_model('institutions', 'Institution')
    for inst in Institution.objects.all():
        inst.name = inst.name_en if inst.name_en else 'Institution'
        inst.save()


class Migration(migrations.Migration):

    dependencies = [
        ('institutions', '0004_alter_institution_options_remove_institution_name_and_more'),
    ]

    operations = [
        # Ajouter le champ name
        migrations.AddField(
            model_name='institution',
            name='name',
            field=models.CharField(default='', max_length=255, verbose_name='Institution Name'),
            preserve_default=False,
        ),
        # Copier les données
        migrations.RunPython(copy_name_en_to_name, migrations.RunPython.noop),
        # Supprimer les anciens champs
        migrations.RemoveField(
            model_name='institution',
            name='name_en',
        ),
        migrations.RemoveField(
            model_name='institution',
            name='name_ar',
        ),
        # Remettre ordering sur 'name'
        migrations.AlterModelOptions(
            name='institution',
            options={'ordering': ['name'], 'verbose_name': 'Institution', 'verbose_name_plural': 'Institutions'},
        ),
    ]
