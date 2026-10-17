from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "packages" / "proofcheck"
FORBIDDEN = {"z3", "z3_solver", "services", "certgen", "generator"}


class ImportBoundaryTests(unittest.TestCase):
    def test_source_imports_only_stdlib_and_proofcheck(self) -> None:
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module.split(".")[0]]
                for module in modules:
                    self.assertNotIn(module, FORBIDDEN, path.name)
                    self.assertIn(module, {"hashlib", "json", "re", "argparse", "sys", "dataclasses", "pathlib", "__future__", "proofcheck"}, path.name)

    def test_runtime_does_not_load_z3(self) -> None:
        env = dict(**{key: value for key, value in __import__("os").environ.items() if key != "PYTHONPATH"})
        env["PYTHONPATH"] = str(ROOT / "packages")
        completed = subprocess.run(
            [sys.executable, "-c", "import sys, proofcheck; raise SystemExit(0 if not any(name.split('.')[0]=='z3' for name in sys.modules) else 1)"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
