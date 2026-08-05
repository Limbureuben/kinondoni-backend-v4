from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0016_remove_reportforward_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='openspace',
            name='shape_type',
            field=models.CharField(default='polygon', max_length=20),
        ),
        migrations.AddField(
            model_name='openspace',
            name='boundary',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='openspace',
            name='area',
            field=models.FloatField(default=0),
        ),
    ]
