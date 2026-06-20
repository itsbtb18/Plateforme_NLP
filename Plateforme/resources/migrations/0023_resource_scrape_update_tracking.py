from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0022_merge_0021_merge_0021_merge_resources_leafs"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="last_scraped_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Last Scraped At"),
        ),
        migrations.AddField(
            model_name="course",
            name="update_counter",
            field=models.PositiveIntegerField(default=0, verbose_name="Update Counter"),
        ),
        migrations.AddField(
            model_name="corpus",
            name="last_scraped_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Last Scraped At"),
        ),
        migrations.AddField(
            model_name="corpus",
            name="update_counter",
            field=models.PositiveIntegerField(default=0, verbose_name="Update Counter"),
        ),
        migrations.AddField(
            model_name="nlptool",
            name="last_scraped_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Last Scraped At"),
        ),
        migrations.AddField(
            model_name="nlptool",
            name="update_counter",
            field=models.PositiveIntegerField(default=0, verbose_name="Update Counter"),
        ),
    ]
