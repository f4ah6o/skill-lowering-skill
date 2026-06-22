from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory.py"
FIXTURE = ROOT / "tests" / "fixtures" / "sample-skill"

spec = importlib.util.spec_from_file_location("inventory", SCRIPT)
assert spec is not None and spec.loader is not None
inventory = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inventory
spec.loader.exec_module(inventory)


class InventoryTest(unittest.TestCase):
    def test_inventory_is_stable(self) -> None:
        first = inventory.build_inventory(FIXTURE)
        second = inventory.build_inventory(FIXTURE)
        self.assertEqual(first, second)
        self.assertEqual(first["skill"]["name"], "sample-review")
        self.assertEqual(len(first["fenced_blocks"]), 1)
        self.assertEqual(first["references"][0]["target"], "scripts/check.py")
        self.assertTrue(first["references"][0]["exists"])

    def test_instruction_candidates_exclude_fenced_command(self) -> None:
        result = inventory.build_inventory(FIXTURE)
        texts = [item["text"] for item in result["instruction_candidates"]]
        self.assertIn("Find all JSON files.", texts)
        self.assertIn("Validate each file.", texts)
        self.assertNotIn('jq empty "$file"', texts)

    def test_cli_json_output(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), str(FIXTURE), "--format", "json"],
            check=True,
            capture_output=True,
            text=True,
        )
        parsed = json.loads(completed.stdout)
        self.assertEqual(parsed["version"], "1")

    def test_missing_skill_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), temporary_directory],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("SKILL.md not found", completed.stderr)


if __name__ == "__main__":
    unittest.main()
