"""Tests for the gamification compute + award service."""

from datetime import date, datetime, timezone as dt_timezone

from django.test import TestCase

from apps.core import gamification
from apps.core.models import (
    Badge,
    Board,
    BoardColumn,
    Milestone,
    Project,
    ProjectMember,
    Sprint,
    SystemRole,
    Task,
    TaskAssignment,
    TaskWarning,
    UserAccount,
    UserBadge,
)


class PureMathTests(TestCase):
    """No DB — exercise the pure XP/level/streak functions."""

    def test_xp_for_task_no_due_date(self):
        self.assertEqual(gamification.xp_for_task(None, date(2026, 1, 1), None), 10)
        self.assertEqual(gamification.xp_for_task(None, date(2026, 1, 1), 5), 15)

    def test_xp_for_task_on_time_same_day(self):
        # Completed exactly on the due date counts as on time (15), plus points.
        self.assertEqual(gamification.xp_for_task(date(2026, 1, 10), date(2026, 1, 10), 3), 18)

    def test_xp_for_task_early(self):
        # >= 1 day before due = early (20).
        self.assertEqual(gamification.xp_for_task(date(2026, 1, 10), date(2026, 1, 5), 0), 20)

    def test_xp_for_task_late(self):
        self.assertEqual(gamification.xp_for_task(date(2026, 1, 10), date(2026, 1, 11), 2), 7)

    def test_level_for_xp(self):
        self.assertEqual(gamification.level_for_xp(0), 1)
        self.assertEqual(gamification.level_for_xp(99), 1)
        self.assertEqual(gamification.level_for_xp(100), 2)
        self.assertEqual(gamification.level_for_xp(400), 3)

    def test_level_thresholds_are_inverse(self):
        self.assertEqual(gamification.xp_threshold_for_level(1), 0)
        self.assertEqual(gamification.xp_threshold_for_level(2), 100)
        self.assertEqual(gamification.xp_threshold_for_level(3), 400)

    def test_level_progress(self):
        p = gamification.level_progress(150)
        self.assertEqual(p["level"], 2)
        self.assertEqual(p["xp_into_level"], 50)   # 150 - 100
        self.assertEqual(p["xp_for_next_level"], 300)  # 400 - 100

    def test_compute_streaks(self):
        # Most-recent-first flags.
        self.assertEqual(gamification.compute_streaks([True, True, False, True]), (2, 2))
        self.assertEqual(gamification.compute_streaks([True, True, True]), (3, 3))
        self.assertEqual(gamification.compute_streaks([False, True, True]), (0, 2))
        self.assertEqual(gamification.compute_streaks([]), (0, 0))


def _dt(y, m, d):
    return datetime(y, m, d, 12, 0, tzinfo=dt_timezone.utc)


class ComputeStatsTests(TestCase):
    def setUp(self):
        self.user_role = SystemRole.objects.create(name=SystemRole.USER)
        self.stake_role = SystemRole.objects.create(name=SystemRole.STAKEHOLDER)
        self.user = UserAccount.objects.create(
            email="dev@example.com", username="dev", password_hash="x", system_role=self.user_role
        )
        self.project = Project.objects.create(name="P1")
        ProjectMember.objects.create(user=self.user, project=self.project)
        board = Board.objects.create(project=self.project, name="B1")
        self.final_col = BoardColumn.objects.create(board=board, name="Done", is_final=True)

    def _completed_task(self, due, completed_at, points=None):
        task = Task.objects.create(
            project=self.project,
            title="T",
            board_column=self.final_col,
            due_date=due,
            story_points=points,
            completed_at=completed_at,  # kept by Task.save since column is final
        )
        TaskAssignment.objects.create(task=task, assigned_to=self.user)
        return task

    def test_on_time_task_xp_and_level(self):
        self._completed_task(date(2026, 1, 10), _dt(2026, 1, 10), points=3)
        stats = gamification.compute_user_stats(self.user)
        self.assertTrue(stats["is_eligible"])
        self.assertEqual(stats["total_xp"], 18)  # 15 on-time + 3 points
        self.assertEqual(stats["level"], 1)
        self.assertEqual(stats["current_streak"], 1)
        self.assertEqual(stats["longest_streak"], 1)

    def test_streak_breaks_on_late_task(self):
        # Most recent two on time, older one late -> current 2, longest 2.
        self._completed_task(date(2026, 1, 5), _dt(2026, 1, 6))   # late (oldest)
        self._completed_task(date(2026, 1, 10), _dt(2026, 1, 10))  # on time
        self._completed_task(date(2026, 1, 20), _dt(2026, 1, 19))  # early (newest)
        stats = gamification.compute_user_stats(self.user)
        self.assertEqual(stats["current_streak"], 2)
        self.assertEqual(stats["longest_streak"], 2)

    def test_stakeholder_is_excluded(self):
        self.user.system_role = self.stake_role
        self.user.save()
        self._completed_task(date(2026, 1, 10), _dt(2026, 1, 10), points=3)
        stats = gamification.compute_user_stats(self.user)
        self.assertFalse(stats["is_eligible"])
        self.assertEqual(stats["total_xp"], 0)

    def test_warning_resolved_adds_xp(self):
        task = self._completed_task(date(2026, 1, 10), _dt(2026, 1, 10))
        TaskWarning.objects.create(task=task, message="x", status=TaskWarning.STATUS_RESOLVED)
        stats = gamification.compute_user_stats(self.user)
        self.assertEqual(stats["total_xp"], 15 + 8)  # on-time + resolved warning


class BadgeAwardTests(TestCase):
    def setUp(self):
        self.user_role = SystemRole.objects.create(name=SystemRole.USER)
        self.user = UserAccount.objects.create(
            email="dev@example.com", username="dev", password_hash="x", system_role=self.user_role
        )
        self.project = Project.objects.create(name="P1")
        ProjectMember.objects.create(user=self.user, project=self.project)
        board = Board.objects.create(project=self.project, name="B1")
        self.final_col = BoardColumn.objects.create(board=board, name="Done", is_final=True)
        # Migrations are disabled under the test settings, so seed the badge we need.
        Badge.objects.create(
            code="FIRST_TASK", name="Primer paso", category="delivery", tier=1, xp_reward=10
        )

    def _completed_task(self):
        task = Task.objects.create(
            project=self.project, title="T", board_column=self.final_col,
            due_date=date(2026, 1, 10), completed_at=_dt(2026, 1, 10),
        )
        TaskAssignment.objects.create(task=task, assigned_to=self.user)
        return task

    def test_first_task_badge_awarded_once_and_idempotent(self):
        self._completed_task()
        awarded = gamification.award_badges(self.user)
        self.assertGreaterEqual(awarded, 1)
        self.assertTrue(
            UserBadge.objects.filter(user=self.user, badge__code="FIRST_TASK", project__isnull=True).exists()
        )
        # Re-running must not double-award.
        again = gamification.award_badges(self.user)
        self.assertEqual(again, 0)
        self.assertEqual(
            UserBadge.objects.filter(user=self.user, badge__code="FIRST_TASK").count(), 1
        )

    def test_badge_xp_reward_folded_into_total(self):
        self._completed_task()
        before = gamification.compute_user_stats(self.user)["total_xp"]
        gamification.award_badges(self.user)
        after = gamification.compute_user_stats(self.user)["total_xp"]
        first_task_reward = Badge.objects.get(code="FIRST_TASK").xp_reward
        self.assertEqual(after - before, first_task_reward)

    def test_no_badge_when_threshold_not_met(self):
        # No completed tasks -> FIRST_TASK not unlocked.
        awarded = gamification.award_badges(self.user)
        self.assertEqual(
            UserBadge.objects.filter(user=self.user, badge__code="FIRST_TASK").count(), 0
        )
        self.assertEqual(awarded, 0)


class LeaderboardTests(TestCase):
    def setUp(self):
        self.user_role = SystemRole.objects.create(name=SystemRole.USER)
        self.stake_role = SystemRole.objects.create(name=SystemRole.STAKEHOLDER)
        self.project = Project.objects.create(name="P1")
        board = Board.objects.create(project=self.project, name="B1")
        self.final_col = BoardColumn.objects.create(board=board, name="Done", is_final=True)

    def _member(self, name, role):
        u = UserAccount.objects.create(
            email=f"{name}@example.com", username=name, password_hash="x", system_role=role
        )
        ProjectMember.objects.create(user=u, project=self.project)
        return u

    def _completed_task(self, user, points):
        task = Task.objects.create(
            project=self.project, title="T", board_column=self.final_col,
            due_date=date(2026, 1, 10), completed_at=_dt(2026, 1, 10), story_points=points,
        )
        TaskAssignment.objects.create(task=task, assigned_to=user)

    def test_ranked_and_excludes_stakeholder(self):
        alice = self._member("alice", self.user_role)
        bob = self._member("bob", self.user_role)
        stake = self._member("stan", self.stake_role)
        self._completed_task(alice, 8)   # more points -> higher xp
        self._completed_task(bob, 1)
        self._completed_task(stake, 99)  # excluded regardless

        rows = gamification.compute_leaderboard(project=self.project)
        usernames = [r["username"] for r in rows]
        self.assertNotIn("stan", usernames)
        self.assertEqual(rows[0]["username"], "alice")
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[1]["username"], "bob")
        self.assertEqual(rows[1]["rank"], 2)
