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
