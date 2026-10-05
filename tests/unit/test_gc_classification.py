from __future__ import annotations

import unittest

from aivp.maintenance.gc import (
    Classification,
    PlannedAction,
    Ownership,
    ResourceFacts,
    classify_resource,
)


CUTOFF = 7 * 24 * 60 * 60


class GCClassificationTests(unittest.TestCase):
    def classify(
        self,
        facts: ResourceFacts,
    ):
        return classify_resource(
            facts,
            older_than_seconds=CUTOFF,
        )

    def test_foreign_resource_is_preserved(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="foreign",
                ownership=Ownership.FOREIGN,
                age_seconds=CUTOFF * 10,
                terminal=True,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.FOREIGN,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.PRESERVE,
        )

    def test_unknown_ownership_is_preserved(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="unknown",
                ownership=Ownership.UNKNOWN,
                age_seconds=CUTOFF * 10,
                terminal=True,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.UNKNOWN,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.PRESERVE,
        )

    def test_protected_resource_beats_expiration(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="evidence",
                ownership=Ownership.AIVP,
                protected=True,
                terminal=True,
                age_seconds=CUTOFF * 10,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.PROTECTED,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.PRESERVE,
        )

    def test_resumable_resource_beats_expiration(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="interrupted",
                ownership=Ownership.AIVP,
                resumable=True,
                age_seconds=CUTOFF * 10,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.RESUMABLE,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.PRESERVE,
        )

    def test_recent_terminal_resource_is_retained(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="recent-terminal",
                ownership=Ownership.AIVP,
                terminal=True,
                age_seconds=CUTOFF - 1,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.TERMINAL_RETAINED,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.PRESERVE,
        )

    def test_expired_terminal_resource_is_candidate(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="expired-terminal",
                ownership=Ownership.AIVP,
                terminal=True,
                age_seconds=CUTOFF,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.EXPIRED,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.GC_CANDIDATE,
        )

    def test_recent_orphan_is_preserved(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="recent-orphan",
                ownership=Ownership.AIVP,
                orphaned=True,
                age_seconds=CUTOFF - 1,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.ORPHANED,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.PRESERVE,
        )

    def test_expired_orphan_is_candidate(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="expired-orphan",
                ownership=Ownership.AIVP,
                orphaned=True,
                age_seconds=CUTOFF,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.ORPHANED,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.GC_CANDIDATE,
        )

    def test_ambiguous_aivp_resource_fails_closed(self):
        decision = self.classify(
            ResourceFacts(
                resource_id="ambiguous",
                ownership=Ownership.AIVP,
                age_seconds=CUTOFF * 10,
            )
        )

        self.assertEqual(
            decision.classification,
            Classification.UNKNOWN,
        )
        self.assertEqual(
            decision.action,
            PlannedAction.PRESERVE,
        )

    def test_orphan_cannot_also_be_resumable(self):
        with self.assertRaises(ValueError):
            ResourceFacts(
                resource_id="contradiction",
                ownership=Ownership.AIVP,
                orphaned=True,
                resumable=True,
            )

    def test_negative_cutoff_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_resource(
                ResourceFacts(
                    resource_id="resource",
                    ownership=Ownership.AIVP,
                ),
                older_than_seconds=-1,
            )


if __name__ == "__main__":
    unittest.main()
