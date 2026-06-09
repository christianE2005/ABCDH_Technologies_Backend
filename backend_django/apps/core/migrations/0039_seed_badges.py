# Seed the badge catalog (spec §6). Idempotent: get_or_create by `code`, so
# re-running won't clobber admin edits, and reverse removes only these codes.

from django.db import migrations

BADGES = [
    # code, name, description, category, tier, icon, xp_reward
    ("FIRST_TASK", "Primer paso", "Completa tu primera tarea.", "delivery", 1, "🎯", 10),
    ("SPRINT_FINISHER", "Sprint cerrado", "Pertenece a un sprint que cerró con ≥80% de sus tareas completadas.", "teamwork", 1, "🏁", 50),
    ("BURNDOWN_HERO", "Burndown Hero", "Pertenece a un sprint que terminó con el 100% de sus tareas completadas.", "teamwork", 1, "📉", 75),
    ("ON_TIME_5", "Puntual", "Racha de 5 tareas entregadas a tiempo.", "delivery", 1, "⏱️", 25),
    ("ON_TIME_15", "Puntual (Plata)", "Racha de 15 tareas entregadas a tiempo.", "delivery", 2, "⏰", 75),
    ("ON_TIME_40", "Puntual (Oro)", "Racha de 40 tareas entregadas a tiempo.", "delivery", 3, "🕰️", 200),
    ("WARNING_SLAYER", "Cazador de alertas", "Resuelve 10 alertas en tus tareas.", "quality", 1, "🛡️", 50),
    ("ESTIMATOR", "Estimador", "Completa 10 tareas con estimación de puntos.", "quality", 1, "📏", 40),
    ("MILESTONE_MAKER", "Hito", "Pertenece a un proyecto que completó un hito.", "milestone", 1, "🏆", 60),
    ("POINT_CRUSHER_100", "Acumulador", "Acumula 100 puntos de historia completados.", "delivery", 1, "💯", 50),
    ("POINT_CRUSHER_500", "Acumulador (Oro)", "Acumula 500 puntos de historia completados.", "delivery", 2, "🔥", 250),
    ("COMMITTED", "Conectado", "Vincula 5 commits a tus tareas.", "teamwork", 1, "🔗", 25),
]


def seed_badges(apps, schema_editor):
    Badge = apps.get_model("core", "Badge")
    for code, name, description, category, tier, icon, xp_reward in BADGES:
        Badge.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "category": category,
                "tier": tier,
                "icon": icon,
                "xp_reward": xp_reward,
                "is_active": True,
            },
        )


def unseed_badges(apps, schema_editor):
    Badge = apps.get_model("core", "Badge")
    Badge.objects.filter(code__in=[b[0] for b in BADGES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0038_badge_userstats_userbadge"),
    ]

    operations = [
        migrations.RunPython(seed_badges, unseed_badges),
    ]
