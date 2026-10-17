from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

from proofcheck import check_certificate  # noqa: E402

VECTORS = ROOT / "tests" / "proofcheck" / "vectors"


class VectorFileTests(unittest.TestCase):
    def test_checked_development_vectors(self) -> None:
        expected = {
            "demo-r1-proved.json": ("PROVED", ("as_api_v2", "as_ready_rule", "as_tests_pass")),
            "demo-r2-refuted.json": ("REFUTED", ("as_block_rule", "as_tests_fail")),
        }
        for name, (result, support) in expected.items():
            payload = json.loads((VECTORS / name).read_text(encoding="utf-8"))
            self.assertTrue(payload["development_fixture"])
            self.assertIn("Not a live service response", payload["notice"])
            report = check_certificate(payload["bundle"], payload["expected_context"])
            self.assertTrue(report.logical_valid, report.to_dict())
            self.assertEqual(report.context_binding, "MATCHED")
            self.assertEqual(payload["bundle"]["result"], result)
            self.assertEqual(report.support_assertion_ids, support)


if __name__ == "__main__":
    unittest.main()
