#!/usr/bin/env python3
"""Validate a Skill Lowering plan and its cross-field invariants."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

CLASSIFICATIONS = (
    "existing-command",
    "bundled-script",
    "keep-agent",
    "human-gate",
    "unsupported",
)
RISKS = ("low", "medium", "high")
VERIFICATION_STATUSES = ("planned", "passed", "failed", "not-possible")
OPERATION_ID_RE = re.compile(r"^op-[0-9]{3,}$")
SUMMARY_KEYS = {
    "total",
    "existing_command",
    "bundled_script",
    "keep_agent",
    "human_gate",
    "unsupported",
}


class PlanValidationError(Exception):
    """Raised when a lowering plan is invalid."""

    def __init__(self, diagnostics: list[str]):
        self.diagnostics = diagnostics
        super().__init__("; ".join(diagnostics))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def load_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PlanValidationError([f"cannot read plan: {path}: {exc}"]) from exc
    except UnicodeDecodeError as exc:
        raise PlanValidationError([f"plan is not valid UTF-8: {path}"]) from exc
    except json.JSONDecodeError as exc:
        raise PlanValidationError(
            [f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"]
        ) from exc
    if not isinstance(value, dict):
        raise PlanValidationError(["plan must be a JSON object"])
    return value


def _require_object(value: Any, location: str, diagnostics: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        diagnostics.append(f"{location}: expected object")
        return None
    return value


def _require_string(
    value: Any, location: str, diagnostics: list[str], *, allow_empty: bool = False
) -> str | None:
    if not isinstance(value, str):
        diagnostics.append(f"{location}: expected string")
        return None
    if not allow_empty and not value.strip():
        diagnostics.append(f"{location}: must not be empty")
        return None
    return value


def _require_string_list(value: Any, location: str, diagnostics: list[str]) -> list[str] | None:
    if not isinstance(value, list):
        diagnostics.append(f"{location}: expected array")
        return None
    if not all(isinstance(item, str) for item in value):
        diagnostics.append(f"{location}: every item must be a string")
        return None
    return value


def _validate_relative_path(value: Any, location: str, diagnostics: list[str]) -> str | None:
    text = _require_string(value, location, diagnostics)
    if text is None:
        return None
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or text.startswith("./"):
        diagnostics.append(f"{location}: must be a normalized relative POSIX path")
    return text


def validate_plan(plan: dict[str, Any]) -> None:
    diagnostics: list[str] = []
    required_top = {"version", "target_skill", "summary", "operations"}
    missing_top = sorted(required_top - set(plan))
    extra_top = sorted(set(plan) - required_top)
    for key in missing_top:
        diagnostics.append(f"plan.{key}: missing required field")
    for key in extra_top:
        diagnostics.append(f"plan.{key}: unexpected field")

    if plan.get("version") != "1":
        diagnostics.append("plan.version: expected literal '1'")

    target = _require_object(plan.get("target_skill"), "plan.target_skill", diagnostics)
    if target is not None:
        expected = {"path", "name"}
        for key in sorted(expected - set(target)):
            diagnostics.append(f"plan.target_skill.{key}: missing required field")
        for key in sorted(set(target) - expected):
            diagnostics.append(f"plan.target_skill.{key}: unexpected field")
        _require_string(target.get("path"), "plan.target_skill.path", diagnostics)
        _require_string(target.get("name"), "plan.target_skill.name", diagnostics)

    summary = _require_object(plan.get("summary"), "plan.summary", diagnostics)
    if summary is not None:
        for key in sorted(SUMMARY_KEYS - set(summary)):
            diagnostics.append(f"plan.summary.{key}: missing required field")
        for key in sorted(set(summary) - SUMMARY_KEYS):
            diagnostics.append(f"plan.summary.{key}: unexpected field")
        for key in sorted(SUMMARY_KEYS & set(summary)):
            value = summary[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                diagnostics.append(f"plan.summary.{key}: expected non-negative integer")

    operations = plan.get("operations")
    if not isinstance(operations, list):
        diagnostics.append("plan.operations: expected array")
        operations = []

    ids: set[str] = set()
    ordering_keys: list[tuple[str, int, str]] = []
    ranges_by_path: dict[str, list[tuple[int, int, str]]] = {}
    actual_counts: Counter[str] = Counter()

    for index, raw_operation in enumerate(operations):
        location = f"plan.operations[{index}]"
        operation = _require_object(raw_operation, location, diagnostics)
        if operation is None:
            continue
        required = {
            "id",
            "source",
            "instruction",
            "classification",
            "risk",
            "confidence",
            "contract",
            "rationale",
            "replacement",
            "verification",
        }
        for key in sorted(required - set(operation)):
            diagnostics.append(f"{location}.{key}: missing required field")
        for key in sorted(set(operation) - required):
            diagnostics.append(f"{location}.{key}: unexpected field")

        operation_id = _require_string(operation.get("id"), f"{location}.id", diagnostics)
        if operation_id is not None:
            if not OPERATION_ID_RE.fullmatch(operation_id):
                diagnostics.append(f"{location}.id: expected pattern op-[0-9]{{3,}}")
            if operation_id in ids:
                diagnostics.append(f"{location}.id: duplicate operation id {operation_id!r}")
            ids.add(operation_id)

        source = _require_object(operation.get("source"), f"{location}.source", diagnostics)
        source_path: str | None = None
        start_line: int | None = None
        end_line: int | None = None
        if source is not None:
            expected = {"path", "start_line", "end_line"}
            for key in sorted(expected - set(source)):
                diagnostics.append(f"{location}.source.{key}: missing required field")
            for key in sorted(set(source) - expected):
                diagnostics.append(f"{location}.source.{key}: unexpected field")
            source_path = _validate_relative_path(
                source.get("path"), f"{location}.source.path", diagnostics
            )
            for field in ("start_line", "end_line"):
                value = source.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                    diagnostics.append(f"{location}.source.{field}: expected positive integer")
                elif field == "start_line":
                    start_line = value
                else:
                    end_line = value
            if start_line is not None and end_line is not None and end_line < start_line:
                diagnostics.append(f"{location}.source: end_line must be >= start_line")
            if source_path and start_line and end_line and operation_id:
                ordering_keys.append((source_path, start_line, operation_id))
                ranges_by_path.setdefault(source_path, []).append(
                    (start_line, end_line, operation_id)
                )

        _require_string(operation.get("instruction"), f"{location}.instruction", diagnostics)

        classification = operation.get("classification")
        if classification not in CLASSIFICATIONS:
            diagnostics.append(
                f"{location}.classification: expected one of {', '.join(CLASSIFICATIONS)}"
            )
        else:
            actual_counts[classification] += 1

        if operation.get("risk") not in RISKS:
            diagnostics.append(f"{location}.risk: expected one of {', '.join(RISKS)}")

        confidence = operation.get("confidence")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            diagnostics.append(f"{location}.confidence: expected number from 0 through 1")

        contract = _require_object(operation.get("contract"), f"{location}.contract", diagnostics)
        if contract is not None:
            expected = {"inputs", "outputs", "side_effects", "failure_behavior"}
            for key in sorted(expected - set(contract)):
                diagnostics.append(f"{location}.contract.{key}: missing required field")
            for key in sorted(set(contract) - expected):
                diagnostics.append(f"{location}.contract.{key}: unexpected field")
            for key in ("inputs", "outputs", "side_effects"):
                _require_string_list(contract.get(key), f"{location}.contract.{key}", diagnostics)
            _require_string(
                contract.get("failure_behavior"),
                f"{location}.contract.failure_behavior",
                diagnostics,
            )

        _require_string(operation.get("rationale"), f"{location}.rationale", diagnostics)

        replacement = operation.get("replacement")
        if classification in {"existing-command", "bundled-script"}:
            replacement_object = _require_object(
                replacement, f"{location}.replacement", diagnostics
            )
            if replacement_object is not None:
                expected = {
                    "kind",
                    "executable",
                    "argv",
                    "cwd",
                    "expected_exit_codes",
                    "fallback",
                }
                for key in sorted(expected - set(replacement_object)):
                    diagnostics.append(f"{location}.replacement.{key}: missing required field")
                for key in sorted(set(replacement_object) - expected):
                    diagnostics.append(f"{location}.replacement.{key}: unexpected field")
                if replacement_object.get("kind") != classification:
                    diagnostics.append(
                        f"{location}.replacement.kind: must match classification {classification!r}"
                    )
                _require_string(
                    replacement_object.get("executable"),
                    f"{location}.replacement.executable",
                    diagnostics,
                )
                _require_string_list(
                    replacement_object.get("argv"),
                    f"{location}.replacement.argv",
                    diagnostics,
                )
                _require_string(
                    replacement_object.get("cwd"),
                    f"{location}.replacement.cwd",
                    diagnostics,
                    allow_empty=True,
                )
                exit_codes = replacement_object.get("expected_exit_codes")
                if (
                    not isinstance(exit_codes, list)
                    or not exit_codes
                    or not all(
                        isinstance(code, int) and not isinstance(code, bool) for code in exit_codes
                    )
                ):
                    diagnostics.append(
                        f"{location}.replacement.expected_exit_codes: expected non-empty integer array"
                    )
                elif len(exit_codes) != len(set(exit_codes)):
                    diagnostics.append(
                        f"{location}.replacement.expected_exit_codes: duplicate exit code"
                    )
                _require_string(
                    replacement_object.get("fallback"),
                    f"{location}.replacement.fallback",
                    diagnostics,
                )
        elif classification in CLASSIFICATIONS and replacement is not None:
            diagnostics.append(
                f"{location}.replacement: must be null for classification {classification!r}"
            )

        verification = _require_object(
            operation.get("verification"), f"{location}.verification", diagnostics
        )
        if verification is not None:
            required_verification = {"method", "status"}
            allowed_verification = required_verification | {"evidence"}
            for key in sorted(required_verification - set(verification)):
                diagnostics.append(f"{location}.verification.{key}: missing required field")
            for key in sorted(set(verification) - allowed_verification):
                diagnostics.append(f"{location}.verification.{key}: unexpected field")
            _require_string(
                verification.get("method"), f"{location}.verification.method", diagnostics
            )
            if verification.get("status") not in VERIFICATION_STATUSES:
                diagnostics.append(
                    f"{location}.verification.status: expected one of "
                    + ", ".join(VERIFICATION_STATUSES)
                )
            if "evidence" in verification:
                _require_string_list(
                    verification.get("evidence"),
                    f"{location}.verification.evidence",
                    diagnostics,
                )

    if ordering_keys != sorted(ordering_keys):
        diagnostics.append(
            "plan.operations: operations must be sorted by source path, start line, then id"
        )

    for source_path, ranges in sorted(ranges_by_path.items()):
        ordered_ranges = sorted(ranges)
        for previous, current in zip(ordered_ranges, ordered_ranges[1:]):
            if current[0] <= previous[1]:
                diagnostics.append(
                    f"plan.operations: overlapping source ranges in {source_path}: "
                    f"{previous[2]} and {current[2]}"
                )

    if summary is not None and all(
        isinstance(summary.get(key), int) and not isinstance(summary.get(key), bool)
        for key in SUMMARY_KEYS
    ):
        expected_summary = {
            "total": len(operations),
            "existing_command": actual_counts["existing-command"],
            "bundled_script": actual_counts["bundled-script"],
            "keep_agent": actual_counts["keep-agent"],
            "human_gate": actual_counts["human-gate"],
            "unsupported": actual_counts["unsupported"],
        }
        for key, expected_value in expected_summary.items():
            if summary.get(key) != expected_value:
                diagnostics.append(
                    f"plan.summary.{key}: expected {expected_value} from operations, "
                    f"got {summary.get(key)!r}"
                )

    if diagnostics:
        raise PlanValidationError(diagnostics)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        plan = load_plan(args.plan)
        validate_plan(plan)
    except PlanValidationError as exc:
        if args.format == "json":
            json.dump(
                {"valid": False, "diagnostics": exc.diagnostics},
                sys.stdout,
                ensure_ascii=False,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            for diagnostic in exc.diagnostics:
                print(f"validate-plan: {diagnostic}", file=sys.stderr)
        return 1

    if args.format == "json":
        json.dump({"valid": True, "diagnostics": []}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
