from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_plan.py"
EXAMPLE = ROOT / "examples" / "lowering-plan.example.json"

spec = importlib.util.spec_from_file_location("validate_plan", SCRIPT)
assert spec is not None and spec.loader is not None
validate_plan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validate_plan
spec.loader.exec_module(validate_plan)


class ValidatePlanTest(unittest.TestCase):
    def load_example(self) -> dict:
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_is_valid(self) -> None:
        validate_plan.validate_plan(self.load_example())

    def test_summary_must_match_operations(self) -> None:
        plan = self.load_example()
        plan["summary"]["total"] = 99
        with self.assertRaises(validate_plan.PlanValidationError) as context:
            validate_plan.validate_plan(plan)
        self.assertIn("plan.summary.total", "\n".join(context.exception.diagnostics))

    def test_replacement_kind_must_match_classification(self) -> None:
        plan = self.load_example()
        plan["operations"][0]["replacement"]["kind"] = "bundled-script"
        with self.assertRaises(validate_plan.PlanValidationError) as context:
            validate_plan.validate_plan(plan)
        self.assertIn("must match classification", "\n".join(context.exception.diagnostics))

    def test_operations_must_be_sorted(self) -> None:
        plan = self.load_example()
        plan["operations"] = list(reversed(plan["operations"]))
        with self.assertRaises(validate_plan.PlanValidationError) as context:
            validate_plan.validate_plan(plan)
        self.assertIn("operations must be sorted", "\n".join(context.exception.diagnostics))

    def test_source_path_must_not_escape(self) -> None:
        plan = self.load_example()
        plan["operations"][0]["source"]["path"] = "../SKILL.md"
        with self.assertRaises(validate_plan.PlanValidationError) as context:
            validate_plan.validate_plan(plan)
        self.assertIn("normalized relative POSIX path", "\n".join(context.exception.diagnostics))


if __name__ == "__main__":
    unittest.main()
