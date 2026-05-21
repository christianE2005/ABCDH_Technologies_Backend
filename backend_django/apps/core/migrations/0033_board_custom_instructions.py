from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_board_response_language"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="board",
                    name="custom_instructions",
                    field=models.TextField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE board ADD COLUMN IF NOT EXISTS custom_instructions text;",
                    reverse_sql="ALTER TABLE board DROP COLUMN IF EXISTS custom_instructions;",
                ),
            ],
        ),
    ]
