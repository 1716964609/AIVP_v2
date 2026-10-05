from __future__ import annotations

import unittest

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from aivp.maintenance.artifact_retention import (
    ArtifactRetentionFacts,
    classify_artifact_retention,
    is_protected_run,
)
from aivp.maintenance.gc import (
    Classification,
    PlannedAction,
)


NOW = datetime(
    2026,
    10,
    5,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

CUTOFF = (
    7
    * 24
    * 60
    * 60
)


class ArtifactRetentionTests(
    unittest.TestCase
):
    def classify(
        self,
        facts: ArtifactRetentionFacts,
    ):
        return classify_artifact_retention(
            facts,
            older_than_seconds=CUTOFF,
            now=NOW,
        )

    def test_explicit_protection_wins_over_legacy_state(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="m8-trial",
                status="RUNNING",
                current_state="VERIFIED",
                finished_at=None,
                has_resume_checkpoint=True,
                protected=True,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.PROTECTED,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )

    def test_protected_prefix_matches_suite_trials(
        self,
    ):
        prefix = (
            "m8-final-routing-"
            "20261004-120728"
        )

        self.assertTrue(
            is_protected_run(
                (
                    prefix
                    + "-001-trial-001"
                ),
                protected_run_prefixes=(
                    prefix,
                ),
            )
        )

        self.assertTrue(
            is_protected_run(
                prefix,
                protected_run_prefixes=(
                    prefix,
                ),
            )
        )

        self.assertFalse(
            is_protected_run(
                prefix + "evil",
                protected_run_prefixes=(
                    prefix,
                ),
            )
        )

    def test_resumable_run_is_preserved(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-resume",
                status="RUNNING",
                current_state="VERIFIED",
                finished_at=None,
                has_resume_checkpoint=True,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.RESUMABLE,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )

    def test_nonterminal_without_checkpoint_is_unknown(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-unknown",
                status="RUNNING",
                current_state="GENERATED",
                finished_at=None,
                has_resume_checkpoint=False,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.UNKNOWN,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )

    def test_recent_terminal_is_retained(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-recent",
                status="AUTO_FINISHED",
                current_state="AUTO_FINISHED",
                finished_at=(
                    NOW
                    - timedelta(
                        days=1
                    )
                ),
                has_resume_checkpoint=False,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.TERMINAL_RETAINED,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )

    def test_old_terminal_is_gc_candidate(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-old",
                status="AUTO_FINISHED",
                current_state="AUTO_FINISHED",
                finished_at=(
                    NOW
                    - timedelta(
                        days=30
                    )
                ),
                has_resume_checkpoint=False,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.EXPIRED,
        )

        self.assertEqual(
            result.action,
            PlannedAction.GC_CANDIDATE,
        )

    def test_human_required_is_retained_even_when_old(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-human",
                status="HUMAN_REQUIRED",
                current_state="HUMAN_REQUIRED",
                finished_at=(
                    NOW
                    - timedelta(
                        days=90
                    )
                ),
                has_resume_checkpoint=False,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.TERMINAL_RETAINED,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )

    def test_terminal_missing_finished_at_fails_closed(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-broken",
                status="AUTO_FINISHED",
                current_state="AUTO_FINISHED",
                finished_at=None,
                has_resume_checkpoint=False,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.UNKNOWN,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )

    def test_terminal_state_mismatch_fails_closed(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-mismatch",
                status="AUTO_FINISHED",
                current_state="VERIFIED",
                finished_at=(
                    NOW
                    - timedelta(
                        days=30
                    )
                ),
                has_resume_checkpoint=False,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.UNKNOWN,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )

    def test_future_terminal_timestamp_fails_closed(
        self,
    ):
        result = self.classify(
            ArtifactRetentionFacts(
                run_id="run-future",
                status="AUTO_FINISHED",
                current_state="AUTO_FINISHED",
                finished_at=(
                    NOW
                    + timedelta(
                        days=1
                    )
                ),
                has_resume_checkpoint=False,
            )
        )

        self.assertEqual(
            result.classification,
            Classification.UNKNOWN,
        )

        self.assertEqual(
            result.action,
            PlannedAction.PRESERVE,
        )


if __name__ == "__main__":
    unittest.main()
