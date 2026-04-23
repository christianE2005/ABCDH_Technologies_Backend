from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_merge_0017_insert_project_roles_0018_taskpushmatch_taskwarning_created_in_push"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS project_repo (
                            id_project_repo BIGSERIAL PRIMARY KEY,
                            id_project BIGINT NOT NULL REFERENCES project(id_project) ON DELETE CASCADE,
                            repo_full_name VARCHAR(255) NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            CONSTRAINT project_repo_unique UNIQUE (id_project, repo_full_name)
                        );

                        INSERT INTO project_repo (id_project, repo_full_name)
                        SELECT id_project, github_repo_full_name
                        FROM project
                        WHERE github_repo_full_name IS NOT NULL AND github_repo_full_name != ''
                        ON CONFLICT DO NOTHING;
                    """,
                    reverse_sql="DROP TABLE IF EXISTS project_repo;",
                )
            ],
            state_operations=[
                migrations.CreateModel(
                    name="ProjectRepo",
                    fields=[
                        ("id_project_repo", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "project",
                            models.ForeignKey(
                                db_column="id_project",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="repos",
                                to="core.project",
                            ),
                        ),
                        ("repo_full_name", models.CharField(max_length=255)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={"db_table": "project_repo"},
                ),
                migrations.AlterUniqueTogether(
                    name="projectrepo",
                    unique_together={("project", "repo_full_name")},
                ),
            ],
        )
    ]
