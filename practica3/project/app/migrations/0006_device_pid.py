from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_alter_device_device_type_alter_device_uid_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='pid',
            field=models.IntegerField(blank=True, null=True, help_text='PID del subproceso del actor'),
        ),
    ]
