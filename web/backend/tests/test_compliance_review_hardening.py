import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main


class ComplianceReviewHardeningTests(unittest.TestCase):
    def test_code_identifier_does_not_match_marketplace_phrase(self):
        self.assertEqual(
            main._collect_risk_keyword_hits("const store = useAppStore();", ("app store",)),
            [],
        )
        self.assertEqual(
            main._collect_risk_keyword_hits("Visit the app store to install the client.", ("app store",)),
            ["app store"],
        )

    def test_ai_suspicion_requires_review_without_escalating_to_high_risk(self):
        result = main._apply_ai_guard_result_to_risk_scan(
            {
                "risk_level": "normal",
                "base_hit_count": 0,
                "hit_count": 0,
                "field_hits": [],
            },
            {
                "suspected": True,
                "action": "block",
                "reason": "AI only suspicion",
                "evidence": ["Unverified external link"],
            },
        )

        self.assertEqual(result["risk_level"], "medium")
        self.assertEqual(result["hit_count"], 0)
        self.assertEqual(result["ai_guard_hit_bonus"], 0)
        self.assertTrue(result["ai_guard_review_suggested"])
        self.assertFalse(result["ai_guard_blocked"])
        with patch.object(main, "RISK_REVIEW_ENABLED", True), patch.object(main, "RISK_REVIEW_ALLOWLIST_CLIENT_IDS", set()):
            self.assertTrue(main._requires_risk_review("client-risk-test", result))

    def test_ai_only_flag_cannot_freeze_client(self):
        risk_scan = {
            "risk_level": "high",
            "base_hit_count": 0,
            "hit_count": 4,
            "combo_blocked": False,
            "ai_guard_blocked": True,
        }

        with patch.object(main, "_get_client_freeze_record", return_value=None), \
            patch.object(main, "_freeze_client_by_ai_risk") as freeze_client:
            result = main._freeze_client_when_risk_blocked(
                client_id="client-risk-test",
                task_id="task-risk-test",
                risk_scan=risk_scan,
                ai_guard_result={"suspected": True, "action": "block"},
            )

        self.assertIsNone(result)
        freeze_client.assert_not_called()

    def test_task_creation_uses_rule_only_freeze_gate(self):
        self.assertNotIn(
            "_is_ai_guard_high_risk(ai_guard_result)",
            inspect.getsource(main.create_task),
        )


if __name__ == "__main__":
    unittest.main()
