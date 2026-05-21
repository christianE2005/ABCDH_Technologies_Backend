from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0029_board_review_focus"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="board",
                    name="tech_stack",
                    field=models.CharField(
                        choices=[
                            ("mixed", "Mixed / Full-Stack"),
                            ("python", "Python"),
                            ("nodejs", "Node.js / JavaScript"),
                            ("typescript", "TypeScript / Node.js"),
                            ("java", "Java / Spring"),
                            ("go", "Go"),
                            ("dotnet", "C# / .NET"),
                            ("react", "React"),
                            ("nextjs", "Next.js"),
                            ("angular", "Angular"),
                            ("vue", "Vue.js"),
                            ("vite", "Vite / Vanilla JS"),
                        ],
                        default="mixed",
                        max_length=20,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE board ADD COLUMN IF NOT EXISTS tech_stack varchar(20) NOT NULL DEFAULT 'mixed';",
                    reverse_sql="ALTER TABLE board DROP COLUMN IF EXISTS tech_stack;",
                ),
            ],
        ),
    ]
