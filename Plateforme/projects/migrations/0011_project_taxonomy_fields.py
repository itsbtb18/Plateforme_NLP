from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("taxonomy", "0001_initial"),
        ("projects", "0010_alter_projectchatmessage_sender_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="datasets",
            field=models.ManyToManyField(blank=True, related_name="projects", to="taxonomy.dataset"),
        ),
        migrations.AddField(
            model_name="project",
            name="nlp_methods",
            field=models.ManyToManyField(blank=True, related_name="projects", to="taxonomy.nlpmethod"),
        ),
        migrations.AddField(
            model_name="project",
            name="research_domains",
            field=models.ManyToManyField(blank=True, related_name="projects", to="taxonomy.researchdomain"),
        ),
    ]

