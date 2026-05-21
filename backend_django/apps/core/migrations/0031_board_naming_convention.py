from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_board_tech_stack"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="board",
                    name="naming_convention",
                    field=models.CharField(
                        choices=[
                            ("default", "Language defaults"),
                            ("camel_case", "camelCase"),
                            ("pascal_case", "PascalCase"),
                            ("snake_case", "snake_case"),
                            ("kebab_case", "kebab-case"),
                            ("mixed", "Mixed (snake_case + camelCase + PascalCase)"),
                        ],
                        default="default",
                        max_length=20,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE board ADD COLUMN IF NOT EXISTS naming_convention varchar(20) NOT NULL DEFAULT 'default';",
                    reverse_sql="ALTER TABLE board DROP COLUMN IF EXISTS naming_convention;",
                ),
            ],
        ),
    ]
