import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Restructures the task system:
    - Adds Sprint, Milestone, Tag, BoardColumn models
    - Removes Task.board (FK to Board) and Task.status (FK to TaskStatus)
    - Adds Task.project (FK to Project, required)
    - Adds Task.sprint, Task.board_column, Task.milestone (nullable FKs)
    - Adds Task.tags (M2M via task_tag table)

    All database operations use IF NOT EXISTS / IF EXISTS to be idempotent
    in production (tables/columns may already exist).
    """

    dependencies = [
        ("core", "0023_merge_0021_activitylog_project_0022_merge"),
    ]

    operations = [
        # ── New standalone models ──────────────────────────────────────────

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Sprint",
                    fields=[
                        ("id_sprint", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "project",
                            models.ForeignKey(
                                db_column="id_project",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="sprints",
                                to="core.project",
                            ),
                        ),
                        ("name", models.CharField(max_length=150)),
                        ("start_date", models.DateField(blank=True, null=True)),
                        ("end_date", models.DateField(blank=True, null=True)),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("planned", "Planned"),
                                    ("active", "Active"),
                                    ("closed", "Closed"),
                                ],
                                default="planned",
                                max_length=20,
                            ),
                        ),
                    ],
                    options={"db_table": "sprint"},
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS sprint (
                            id_sprint bigserial PRIMARY KEY,
                            id_project bigint NOT NULL REFERENCES project(id_project) ON DELETE CASCADE,
                            name varchar(150) NOT NULL,
                            start_date date,
                            end_date date,
                            status varchar(20) NOT NULL DEFAULT 'planned'
                        );
                    """,
                    reverse_sql="DROP TABLE IF EXISTS sprint;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Milestone",
                    fields=[
                        ("id_milestone", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "project",
                            models.ForeignKey(
                                db_column="id_project",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="milestones",
                                to="core.project",
                            ),
                        ),
                        ("name", models.CharField(max_length=150)),
                        ("description", models.TextField(blank=True, null=True)),
                        ("due_date", models.DateField(blank=True, null=True)),
                        ("is_completed", models.BooleanField(default=False)),
                    ],
                    options={"db_table": "milestone"},
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS milestone (
                            id_milestone bigserial PRIMARY KEY,
                            id_project bigint NOT NULL REFERENCES project(id_project) ON DELETE CASCADE,
                            name varchar(150) NOT NULL,
                            description text,
                            due_date date,
                            is_completed boolean NOT NULL DEFAULT false
                        );
                    """,
                    reverse_sql="DROP TABLE IF EXISTS milestone;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Tag",
                    fields=[
                        ("id_tag", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "project",
                            models.ForeignKey(
                                db_column="id_project",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="tags",
                                to="core.project",
                            ),
                        ),
                        ("name", models.CharField(max_length=100)),
                        ("color", models.CharField(blank=True, max_length=20, null=True)),
                    ],
                    options={
                        "db_table": "tag",
                        "unique_together": {("project", "name")},
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS tag (
                            id_tag bigserial PRIMARY KEY,
                            id_project bigint NOT NULL REFERENCES project(id_project) ON DELETE CASCADE,
                            name varchar(100) NOT NULL,
                            color varchar(20),
                            UNIQUE(id_project, name)
                        );
                    """,
                    reverse_sql="DROP TABLE IF EXISTS tag;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="BoardColumn",
                    fields=[
                        ("id_column", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "board",
                            models.ForeignKey(
                                db_column="id_board",
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="columns",
                                to="core.board",
                            ),
                        ),
                        ("name", models.CharField(max_length=100)),
                        ("order", models.PositiveIntegerField(default=0)),
                        ("is_final", models.BooleanField(default=False)),
                    ],
                    options={
                        "db_table": "board_column",
                        "ordering": ["order"],
                    },
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS board_column (
                            id_column bigserial PRIMARY KEY,
                            id_board bigint NOT NULL REFERENCES board(id_board) ON DELETE CASCADE,
                            name varchar(100) NOT NULL,
                            "order" integer NOT NULL DEFAULT 0,
                            is_final boolean NOT NULL DEFAULT false
                        );
                    """,
                    reverse_sql="DROP TABLE IF EXISTS board_column;",
                ),
            ],
        ),

        # ── Modify Task: remove old FK columns ───────────────────────────

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="task", name="board"),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE task DROP COLUMN IF EXISTS id_board;",
                    reverse_sql="ALTER TABLE task ADD COLUMN IF NOT EXISTS id_board bigint REFERENCES board(id_board) ON DELETE CASCADE;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="task", name="status"),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE task DROP COLUMN IF EXISTS id_status;",
                    reverse_sql="ALTER TABLE task ADD COLUMN IF NOT EXISTS id_status bigint REFERENCES task_status(id_status) ON DELETE SET NULL;",
                ),
            ],
        ),

        # ── Modify Task: add new FK columns ──────────────────────────────

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="task",
                    name="project",
                    field=models.ForeignKey(
                        db_column="id_project",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="core.project",
                        null=True,
                        blank=True,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE task ADD COLUMN IF NOT EXISTS id_project bigint REFERENCES project(id_project) ON DELETE CASCADE;",
                    reverse_sql="ALTER TABLE task DROP COLUMN IF EXISTS id_project;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="task",
                    name="sprint",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="id_sprint",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tasks",
                        to="core.sprint",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE task ADD COLUMN IF NOT EXISTS id_sprint bigint REFERENCES sprint(id_sprint) ON DELETE SET NULL;",
                    reverse_sql="ALTER TABLE task DROP COLUMN IF EXISTS id_sprint;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="task",
                    name="board_column",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="id_column",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tasks",
                        to="core.boardcolumn",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE task ADD COLUMN IF NOT EXISTS id_column bigint REFERENCES board_column(id_column) ON DELETE SET NULL;",
                    reverse_sql="ALTER TABLE task DROP COLUMN IF EXISTS id_column;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="task",
                    name="milestone",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="id_milestone",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tasks",
                        to="core.milestone",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE task ADD COLUMN IF NOT EXISTS id_milestone bigint REFERENCES milestone(id_milestone) ON DELETE SET NULL;",
                    reverse_sql="ALTER TABLE task DROP COLUMN IF EXISTS id_milestone;",
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="task",
                    name="tags",
                    field=models.ManyToManyField(
                        blank=True,
                        db_table="task_tag",
                        related_name="tasks",
                        to="core.tag",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE TABLE IF NOT EXISTS task_tag (
                            id bigserial PRIMARY KEY,
                            task_id bigint NOT NULL REFERENCES task(id_task) ON DELETE CASCADE,
                            tag_id bigint NOT NULL REFERENCES tag(id_tag) ON DELETE CASCADE,
                            UNIQUE(task_id, tag_id)
                        );
                    """,
                    reverse_sql="DROP TABLE IF EXISTS task_tag;",
                ),
            ],
        ),

        # Make task.project non-nullable after data migration step
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="task",
                    name="project",
                    field=models.ForeignKey(
                        db_column="id_project",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="core.project",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        DO $$
                        BEGIN
                            ALTER TABLE task ALTER COLUMN id_project SET NOT NULL;
                        EXCEPTION
                            WHEN not_null_violation THEN NULL;
                        END $$;
                    """,
                    reverse_sql="ALTER TABLE task ALTER COLUMN id_project DROP NOT NULL;",
                ),
            ],
        ),
    ]
