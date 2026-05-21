from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_board_naming_convention"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="board",
                    name="response_language",
                    field=models.CharField(
                        choices=[
                            ("es", "Español"),
                            ("en", "English"),
                        ],
                        default="es",
                        max_length=5,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE board ADD COLUMN IF NOT EXISTS response_language varchar(5) NOT NULL DEFAULT 'es';",
                    reverse_sql="ALTER TABLE board DROP COLUMN IF EXISTS response_language;",
                ),
            ],
        ),
    ]
