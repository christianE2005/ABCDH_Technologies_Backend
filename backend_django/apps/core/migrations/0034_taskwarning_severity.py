from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_board_custom_instructions"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="taskwarning",
                    name="severity",
                    field=models.CharField(
                        choices=[
                            ("critical", "Critical"),
                            ("warning", "Warning"),
                            ("info", "Info"),
                        ],
                        default="warning",
                        max_length=10,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE task_warning ADD COLUMN IF NOT EXISTS severity varchar(10) NOT NULL DEFAULT 'warning';",
                    reverse_sql="ALTER TABLE task_warning DROP COLUMN IF EXISTS severity;",
                ),
            ],
        ),
    ]
