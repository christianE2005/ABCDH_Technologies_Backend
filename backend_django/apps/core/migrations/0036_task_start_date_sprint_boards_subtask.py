from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_project_review_branches"),
    ]

    operations = [
        # 1. Add start_date to Task
        migrations.AddField(
            model_name="task",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        # 2. Create SprintBoard through table
        migrations.CreateModel(
            name="SprintBoard",
            fields=[
                ("id_sprint_board", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "sprint",
                    models.ForeignKey(
                        db_column="id_sprint",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sprint_boards",
                        to="core.sprint",
                    ),
                ),
                (
                    "board",
                    models.ForeignKey(
                        db_column="id_board",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sprint_boards",
                        to="core.board",
                    ),
                ),
            ],
            options={"db_table": "sprint_board"},
        ),
        migrations.AlterUniqueTogether(
            name="sprintboard",
            unique_together={("sprint", "board")},
        ),
        # 3. Add boards M2M field to Sprint (via through model)
        migrations.AddField(
            model_name="sprint",
            name="boards",
            field=models.ManyToManyField(
                blank=True,
                related_name="sprints",
                through="core.SprintBoard",
                to="core.board",
            ),
        ),
        # 4. Create Subtask model
        migrations.CreateModel(
            name="Subtask",
            fields=[
                ("id_subtask", models.BigAutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, null=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_completed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parent_task",
                    models.ForeignKey(
                        db_column="id_task",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subtasks",
                        to="core.task",
                    ),
                ),
            ],
            options={"db_table": "subtask", "ordering": ["order"]},
        ),
    ]
