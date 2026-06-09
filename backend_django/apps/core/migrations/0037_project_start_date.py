from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_task_start_date_sprint_boards_subtask"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
