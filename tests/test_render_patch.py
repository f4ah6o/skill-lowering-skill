from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("render_patch", SCRIPTS / "render_patch.py")
assert spec is not None and spec.loader is not None
render_patch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = render_patch
spec.loader.exec_module(render_patch)


def make_plan(instruction: str = "Validate every JSON file.") -> dict:
    return {
        "version": "1",
        "target_skill": {"path": "sample", "name": "sample"},
        "summary": {
            "total": 1,
            "existing_command": 1,
            "bundled_script": 0,
            "keep_agent": 0,
            "human_gate": 0,
            "unsupported": 0,
        },
        "operations": [
            {
                "id": "op-001",
                "source": {"path": "SKILL.md", "start_line": 6, "end_line": 6},
                "instruction": instruction,
                "classification": "existing-command",
                "risk": "low",
                "confidence": 0.99,
                "contract": {
                    "inputs": ["JSON files"],
                    "outputs": ["diagnostics"],
                    "side_effects": [],
                    "failure_behavior": "Return non-zero for invalid input.",
                },
                "rationale": "Syntax validation is mechanical.",
                "replacement": {
                    "kind": "existing-command",
                    "executable": "jq",
                    "argv": ["empty", "${file}"],
                    "cwd": "${repository_root}",
                    "expected_exit_codes": [0, 4],
                    "fallback": "Report that jq is unavailable.",
                },
                "verification": {
                    "method": "Run valid and malformed fixtures.",
                    "status": "planned",
                    "evidence": [],
                },
            }
        ],
    }


class RenderPatchTest(unittest.TestCase):
    def create_skill(self, root: Path) -> None:
        (root / "SKILL.md").write_text(
            "---\n"
            "name: sample\n"
            "description: sample\n"
            "---\n"
            "\n"
            "- Validate every JSON file.\n",
            encoding="utf-8",
        )

    def test_renders_review_only_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_skill(root)
            patch = render_patch.render_patch(root, make_plan())
        self.assertIn("--- a/SKILL.md", patch)
        self.assertIn('Lowered argv: `["jq", "empty", "${file}"]`', patch)
        self.assertIn("Accepted exit codes: `[0, 4]`", patch)

    def test_rejects_stale_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_skill(root)
            with self.assertRaises(render_patch.RenderError) as context:
                render_patch.render_patch(root, make_plan("Validate YAML files."))
        self.assertIn("no longer matches", str(context.exception))

    def test_can_select_one_operation_from_mixed_plan(self) -> None:
        plan = make_plan()
        second = json.loads(json.dumps(plan["operations"][0]))
        second["id"] = "op-002"
        second["source"] = {"path": "SKILL.md", "start_line": 7, "end_line": 7}
        second["instruction"] = "This paragraph cannot be rendered automatically."
        plan["operations"].append(second)
        plan["summary"]["total"] = 2
        plan["summary"]["existing_command"] = 2
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_skill(root)
            (root / "SKILL.md").write_text(
                (root / "SKILL.md").read_text(encoding="utf-8")
                + "This paragraph cannot be rendered automatically.\n",
                encoding="utf-8",
            )
            patch = render_patch.render_patch(root, plan, {"op-001"})
        self.assertIn("Lowered argv", patch)
        self.assertEqual(patch.count("Lowered argv"), 1)

    def test_rejects_unknown_selected_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_skill(root)
            with self.assertRaises(render_patch.RenderError) as context:
                render_patch.render_patch(root, make_plan(), {"op-999"})
        self.assertIn("unknown operation ID", str(context.exception))

    def test_rejects_selected_keep_agent_operation(self) -> None:
        plan = make_plan()
        plan["operations"][0]["classification"] = "keep-agent"
        plan["operations"][0]["replacement"] = None
        plan["summary"]["existing_command"] = 0
        plan["summary"]["keep_agent"] = 1
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_skill(root)
            with self.assertRaises(render_patch.RenderError) as context:
                render_patch.render_patch(root, plan, {"op-001"})
        self.assertIn("has no command replacement", str(context.exception))

    def test_does_not_modify_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_skill(root)
            before = (root / "SKILL.md").read_text(encoding="utf-8")
            render_patch.render_patch(root, make_plan())
            after = (root / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
