"""
Gamification compute + award service.

Everything here is *derived* from data the platform already stores (tasks, sprints,
warnings, project members, push matches). The only persisted gamification state is
badge unlocks (UserBadge) and an optional stats snapshot (UserStats).

Design goals (see gamification-backend-spec.md):
- Deterministic & idempotent: same source data -> same result; re-running recompute
  never double-awards or changes totals.
- Pure, testable math: XP/level/streak are plain functions over simple inputs.
- Role-aware: stakeholders are excluded from XP and leaderboards.
"""

import math
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import (
    Badge,
    Milestone,
    Sprint,
    Task,
    TaskPushMatch,
    TaskWarning,
    UserBadge,
    UserStats,
)

# ---------------------------------------------------------------------------
# Tunable constants (see spec §3). Keep these in one place so they are easy to tune.
# ---------------------------------------------------------------------------
XP_TASK_DONE = 10            # completed, no due date
XP_TASK_ON_TIME = 15         # completed on or before due date (same-day counts)
XP_TASK_EARLY = 20           # completed >= 1 day before due date
XP_TASK_LATE = 5             # completed after due date
XP_WARNING_RESOLVED = 8      # per resolved warning on the user's task
XP_COMMIT_LINKED = 5         # per commit/push linked to the user's task
XP_SPRINT_CLOSED = 25        # per qualifying sprint, to each member
COMMITS_XP_CAP_PER_DAY = 5   # max commit-XP events counted per calendar day (anti-spam)
SPRINT_DONE_THRESHOLD = 0.8  # >= 80% of a sprint's tasks done = team reward

STAKEHOLDER_ROLE_NAME = "Stakeholder"


# ---------------------------------------------------------------------------
# Pure math — no DB access, unit-testable in isolation.
# ---------------------------------------------------------------------------
def xp_for_task(due_date, completed_date, story_points) -> int:
    """
    XP for a single completed task.

    `completed_date` / `due_date` are date objects. Story-point weight is added on
    top so a heavier task is always worth more than a lighter one.
    """
    points = story_points or 0
    if due_date is None:
        return XP_TASK_DONE + points
    if completed_date <= due_date - timedelta(days=1):
        base = XP_TASK_EARLY
    elif completed_date <= due_date:
        base = XP_TASK_ON_TIME
    else:
        base = XP_TASK_LATE
    return base + points


def level_for_xp(total_xp: int) -> int:
    """level = floor(sqrt(total_xp / 100)) + 1 (spec §4)."""
    if total_xp <= 0:
        return 1
    return int(math.floor(math.sqrt(total_xp / 100.0))) + 1


def xp_threshold_for_level(level: int) -> int:
    """Minimum total_xp required to be at `level` (inverse of level_for_xp)."""
    if level <= 1:
        return 0
    return int((level - 1) ** 2 * 100)


def level_progress(total_xp: int) -> dict:
    """Return level + progress within the current level for a frontend XP bar."""
    level = level_for_xp(total_xp)
    current_floor = xp_threshold_for_level(level)
    next_floor = xp_threshold_for_level(level + 1)
    return {
        "level": level,
        "xp_into_level": total_xp - current_floor,
        "xp_for_next_level": next_floor - current_floor,
    }


def compute_streaks(ontime_flags) -> tuple:
    """
    Given an iterable of booleans ordered most-recent-first (each = "was this
    completed on time?"), return (current_streak, longest_streak).

    Tasks without a due date must be excluded by the caller (they neither break nor
    extend the streak).
    """
    flags = list(ontime_flags)
    current = 0
    for ok in flags:
        if ok:
            current += 1
        else:
            break
    longest = 0
    run = 0
    for ok in flags:
        if ok:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return current, longest


# ---------------------------------------------------------------------------
# Eligibility (role handling — spec §8)
# ---------------------------------------------------------------------------
def is_eligible(user) -> bool:
    """Stakeholders (system role) are read-only observers -> excluded from gamification."""
    role = getattr(user, "system_role", None)
    if role is not None and role.name == STAKEHOLDER_ROLE_NAME:
        return False
    return True


# ---------------------------------------------------------------------------
# Metric gathering (DB) + stat computation
# ---------------------------------------------------------------------------
def _gather_metrics(user, project=None, sprint=None) -> dict:
    """Collect the raw counts/values used by both XP and badge evaluation.

    `project` / `sprint` narrow the scope (used by per-project / per-sprint
    leaderboards). With both None the scope is the user's entire history (global
    profile + badges).
    """
    def scope(prefix=""):
        f = Q()
        if project is not None:
            f &= Q(**{f"{prefix}project": project})
        if sprint is not None:
            f &= Q(**{f"{prefix}sprint": sprint})
        return f

    # Completed tasks assigned to this user (distinct: a task may have many assignments).
    tasks = (
        Task.objects.filter(assignments__assigned_to=user, completed_at__isnull=False)
        .filter(scope())
        .distinct()
        .values("id_task", "due_date", "completed_at", "story_points")
    )
    tasks = list(tasks)

    task_xp = 0
    lifetime_points = 0
    estimated_completed = 0
    # (completed_at, on_time) for streak, most-recent-first, due-date tasks only.
    ontime_history = []
    for t in tasks:
        completed_date = t["completed_at"].date()
        due = t["due_date"]
        task_xp += xp_for_task(due, completed_date, t["story_points"])
        lifetime_points += t["story_points"] or 0
        if t["story_points"] is not None:
            estimated_completed += 1
        if due is not None:
            ontime_history.append((t["completed_at"], completed_date <= due))

    ontime_history.sort(key=lambda x: x[0], reverse=True)
    current_streak, longest_streak = compute_streaks(flag for _, flag in ontime_history)

    # Resolved warnings on the user's tasks.
    resolved_warnings = (
        TaskWarning.objects.filter(
            task__assignments__assigned_to=user,
            status=TaskWarning.STATUS_RESOLVED,
        )
        .filter(scope("task__"))
        .distinct()
        .count()
    )

    # Commits linked to the user's tasks (via TaskPushMatch), capped per day.
    matches = (
        TaskPushMatch.objects.filter(task__assignments__assigned_to=user)
        .filter(scope("task__"))
        .select_related("push")
        .distinct()
    )
    linked_commits = 0
    per_day: dict = {}
    for m in matches:
        linked_commits += 1
        day = m.push.received_at.date() if m.push and m.push.received_at else None
        per_day[day] = per_day.get(day, 0) + 1
    commit_xp = sum(min(count, COMMITS_XP_CAP_PER_DAY) * XP_COMMIT_LINKED for count in per_day.values())

    # Sprints the user participates in that closed with >= threshold done.
    member_project_ids = list(
        user.project_memberships.values_list("project_id", flat=True)
    )
    sprint_qs = Sprint.objects.filter(status=Sprint.CLOSED, project_id__in=member_project_ids)
    if project is not None:
        sprint_qs = sprint_qs.filter(project=project)
    qualifying_sprints = 0
    perfect_sprints = 0
    for sprint in sprint_qs:
        total = Task.objects.filter(sprint=sprint).count()
        if total == 0:
            continue
        done = Task.objects.filter(sprint=sprint, completed_at__isnull=False).count()
        ratio = done / total
        if ratio >= SPRINT_DONE_THRESHOLD:
            qualifying_sprints += 1
        if ratio >= 1.0:
            perfect_sprints += 1

    # Milestones completed in projects the user belongs to.
    milestone_qs = Milestone.objects.filter(is_completed=True, project_id__in=member_project_ids)
    if project is not None:
        milestone_qs = milestone_qs.filter(project=project)
    milestones_completed = milestone_qs.count()

    derived_xp = (
        task_xp
        + XP_WARNING_RESOLVED * resolved_warnings
        + commit_xp
        + XP_SPRINT_CLOSED * qualifying_sprints
    )

    return {
        "completed_tasks": len(tasks),
        "derived_xp": derived_xp,
        "lifetime_points": lifetime_points,
        "estimated_completed": estimated_completed,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "resolved_warnings": resolved_warnings,
        "linked_commits": linked_commits,
        "qualifying_sprints": qualifying_sprints,
        "perfect_sprints": perfect_sprints,
        "milestones_completed": milestones_completed,
    }


def compute_user_stats(user, project=None, sprint=None, include_badge_xp=None) -> dict:
    """
    Compute a user's gamification profile from source data.

    Returns the exact shape the frontend profile endpoint consumes. For the global
    profile (no scope) lifetime badge-reward XP is folded in so totals stay stable
    and idempotent across recomputes. Scoped (project/sprint) views omit badge XP so
    leaderboards are resettable and newcomers aren't permanently behind (spec §7).
    """
    if not is_eligible(user):
        return {
            "total_xp": 0,
            "level": 1,
            "xp_into_level": 0,
            "xp_for_next_level": xp_threshold_for_level(2),
            "current_streak": 0,
            "longest_streak": 0,
            "is_eligible": False,
        }

    if include_badge_xp is None:
        include_badge_xp = project is None and sprint is None

    metrics = _gather_metrics(user, project, sprint)

    badge_xp = 0
    if include_badge_xp:
        badge_xp = sum(
            ub.badge.xp_reward
            for ub in UserBadge.objects.filter(
                user=user, badge__is_active=True, project__isnull=True
            ).select_related("badge")
        )

    total_xp = metrics["derived_xp"] + badge_xp
    progress = level_progress(total_xp)

    return {
        "total_xp": total_xp,
        "level": progress["level"],
        "xp_into_level": progress["xp_into_level"],
        "xp_for_next_level": progress["xp_for_next_level"],
        "current_streak": metrics["current_streak"],
        "longest_streak": metrics["longest_streak"],
        "is_eligible": True,
    }


def compute_leaderboard(project=None, sprint=None) -> list:
    """
    Ranked list of eligible members for a project (optionally a sprint).

    Stakeholders are excluded. Returns rows ordered by total_xp desc with a 1-based
    `rank`. Ties share neither rank slot nor order guarantees beyond xp.
    """
    from .models import UserAccount

    if sprint is not None and project is None:
        project = sprint.project

    if project is not None:
        users = (
            UserAccount.objects.filter(project_memberships__project=project)
            .select_related("system_role")
            .distinct()
        )
    else:
        users = UserAccount.objects.select_related("system_role").all()

    rows = []
    for user in users:
        if not is_eligible(user):
            continue
        stats = compute_user_stats(user, project=project, sprint=sprint)
        rows.append(
            {
                "user": user.id_user,
                "username": user.username,
                "total_xp": stats["total_xp"],
                "level": stats["level"],
            }
        )

    rows.sort(key=lambda r: r["total_xp"], reverse=True)
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


# ---------------------------------------------------------------------------
# Badge catalog + evaluation (spec §6)
# ---------------------------------------------------------------------------
# Each entry: code -> (progress_fn(metrics) -> int, threshold). A badge is unlocked
# the first time progress >= threshold. All v1 badges are global (project=None).
BADGE_RULES = {
    "FIRST_TASK": (lambda m: m["completed_tasks"], 1),
    "SPRINT_FINISHER": (lambda m: m["qualifying_sprints"], 1),
    "BURNDOWN_HERO": (lambda m: m["perfect_sprints"], 1),
    "ON_TIME_5": (lambda m: m["longest_streak"], 5),
    "ON_TIME_15": (lambda m: m["longest_streak"], 15),
    "ON_TIME_40": (lambda m: m["longest_streak"], 40),
    "WARNING_SLAYER": (lambda m: m["resolved_warnings"], 10),
    "ESTIMATOR": (lambda m: m["estimated_completed"], 10),
    "MILESTONE_MAKER": (lambda m: m["milestones_completed"], 1),
    "POINT_CRUSHER_100": (lambda m: m["lifetime_points"], 100),
    "POINT_CRUSHER_500": (lambda m: m["lifetime_points"], 500),
    "COMMITTED": (lambda m: m["linked_commits"], 5),
}


def evaluate_badges(user, metrics=None) -> dict:
    """
    Return {code: {"progress": int, "threshold": int, "unlocked": bool}} for every
    active badge that has a rule. Pure read — does not persist anything.
    """
    if metrics is None:
        metrics = _gather_metrics(user)
    active_codes = set(
        Badge.objects.filter(is_active=True).values_list("code", flat=True)
    )
    result = {}
    for code, (progress_fn, threshold) in BADGE_RULES.items():
        if code not in active_codes:
            continue
        progress = int(progress_fn(metrics))
        result[code] = {
            "progress": progress,
            "threshold": threshold,
            "unlocked": progress >= threshold,
        }
    return result


def award_badges(user, metrics=None) -> int:
    """
    Insert a UserBadge for each newly-unlocked badge (idempotent via unique
    constraint). Returns the number of badges newly awarded. Never revokes.
    """
    if not is_eligible(user):
        return 0
    if metrics is None:
        metrics = _gather_metrics(user)

    badges_by_code = {b.code: b for b in Badge.objects.filter(is_active=True)}
    already = set(
        UserBadge.objects.filter(user=user, project__isnull=True).values_list("badge__code", flat=True)
    )
    awarded = 0
    evaluation = evaluate_badges(user, metrics)
    for code, info in evaluation.items():
        if not info["unlocked"] or code in already:
            continue
        badge = badges_by_code.get(code)
        if badge is None:
            continue
        _, created = UserBadge.objects.get_or_create(
            user=user,
            badge=badge,
            project=None,
            defaults={"progress": info["progress"]},
        )
        if created:
            awarded += 1
    return awarded


def refresh_user_stats(user) -> UserStats:
    """Persist a snapshot of the user's computed stats (cache for leaderboards)."""
    stats = compute_user_stats(user)
    obj, _ = UserStats.objects.update_or_create(
        user=user,
        defaults={
            "total_xp": stats["total_xp"],
            "level": stats["level"],
            "current_streak": stats["current_streak"],
            "longest_streak": stats["longest_streak"],
        },
    )
    return obj
