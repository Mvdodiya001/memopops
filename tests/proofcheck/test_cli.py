from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "proofcheck" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bundles import chain_proved_bundle, context_for  # noqa: E402


class CliTests(unittest.TestCase):
    def test_valid_certificate_without_context_reports_unverified_provenance(self) -> None:
        report, code = self._run(chain_proved_bundle())
        self.assertEqual(code, 0)
        self.assertTrue(report["logical_valid"])
        self.assertEqual(report["context_binding"], "UNVERIFIED")
        self.assertIn("Provenance unverified", report["message"])

    def test_matching_context_exits_zero(self) -> None:
        bundle = chain_proved_bundle()
        report, code = self._run(bundle, context_for(bundle))
        self.assertEqual(code, 0, report)
        self.assertEqual(report["context_binding"], "MATCHED")

    def test_tampered_certificate_exits_one(self) -> None:
        bundle = chain_proved_bundle()
        bundle["clauses"][14]["pivot"] = 1
        _report, code = self._run(bundle)
        self.assertEqual(code, 1)

    def test_context_mismatch_exits_one(self) -> None:
        bundle = chain_proved_bundle()
        context = context_for(bundle)
        context["workspace_id"] = "workspace_other"
        report, code = self._run(bundle, context)
        self.assertEqual(code, 1)
        self.assertTrue(report["logical_valid"])
        self.assertEqual(report["context_binding"], "MISMATCH")

    def test_missing_file_exits_two(self) -> None:
        completed = self._command([str(ROOT / "missing-certificate.json")])
        self.assertEqual(completed.returncode, 2)
        report = json.loads(completed.stdout)
        self.assertFalse(report["logical_valid"])
        self.assertIn("Provenance unverified", report["message"])

    def _run(self, bundle: dict, context: dict | None = None) -> tuple[dict, int]:
        with tempfile.TemporaryDirectory() as directory:
            certificate_path = Path(directory) / "certificate.json"
            certificate_path.write_text(json.dumps(bundle), encoding="utf-8")
            command = [str(certificate_path)]
            if context is not None:
                context_path = Path(directory) / "context.json"
                context_path.write_text(json.dumps(context), encoding="utf-8")
                command.extend(["--expected-context", str(context_path)])
            completed = self._command(command)
        report = json.loads(completed.stdout)
        return report, completed.returncode

    def _command(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "packages" / "proofcheck" / "src")
        return subprocess.run(
            [sys.executable, "-m", "proofcheck", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
