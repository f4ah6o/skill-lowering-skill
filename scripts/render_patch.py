#!/usr/bin/env python3
"""Render a review-only unified diff from a validated Skill Lowering plan."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

from validate_plan import PlanValidationError, load_plan, validate_plan

LIST_ITEM_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>(?:[-*+] |\d+[.)]\s+))(?P<body>.*)$")


class RenderError(Exception):
    """Raised when a plan cannot be rendered safely."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_directory", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--operation",
        action="append",
        dest="operation_ids",
        metavar="ID",
        help="render only the selected operation ID; may be repeated",
    )
    return parser.parse_args(argv)


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def command_argv(replacement: dict[str, Any]) -> list[str]:
    return [replacement["executable"], *replacement["argv"]]


def render_list_item(operation: dict[str, Any], original_line: str) -> list[str]:
    match = LIST_ITEM_RE.match(original_line.rstrip("\n"))
    if match is None:
        raise RenderError(
            f"{operation['id']}: automatic rendering supports single-line Markdown list items only"
        )
    instruction = operation["instruction"]
    if normalize_text(match.group("body")) != normalize_text(instruction):
        raise RenderError(
            f"{operation['id']}: source text no longer matches the planned instruction"
        )

    replacement = operation["replacement"]
    assert isinstance(replacement, dict)
    indent = match.group("indent")
    marker = match.group("marker")
    child_indent = indent + " " * len(marker)
    argv_json = json.dumps(command_argv(replacement), ensure_ascii=False)
    exit_codes = json.dumps(replacement["expected_exit_codes"])
    cwd_json = json.dumps(replacement["cwd"], ensure_ascii=False)

    return [
        f"{indent}{marker}{instruction}\n",
        f"{child_indent}- Lowered argv: `{argv_json}`\n",
        f"{child_indent}- Working directory: `{cwd_json}`\n",
        f"{child_indent}- Accepted exit codes: `{exit_codes}`\n",
        f"{child_indent}- Fallback: {replacement['fallback']}\n",
    ]


def safe_source_path(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RenderError(f"source path escapes skill directory: {relative_path}") from exc
    return candidate


def render_patch(
    skill_directory: Path,
    plan: dict[str, Any],
    operation_ids: set[str] | None = None,
) -> str:
    validate_plan(plan)
    root = skill_directory.resolve()
    if not root.is_dir():
        raise RenderError(f"not a directory: {skill_directory}")

    operations_by_id = {operation["id"]: operation for operation in plan["operations"]}
    if operation_ids is not None:
        unknown_ids = sorted(operation_ids - set(operations_by_id))
        if unknown_ids:
            raise RenderError(f"unknown operation ID(s): {', '.join(unknown_ids)}")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for operation in plan["operations"]:
        if operation_ids is not None and operation["id"] not in operation_ids:
            continue
        if operation["classification"] not in {"existing-command", "bundled-script"}:
            if operation_ids is not None:
                raise RenderError(
                    f"{operation['id']}: classification {operation['classification']!r} "
                    "has no command replacement to render"
                )
            continue
        grouped.setdefault(operation["source"]["path"], []).append(operation)

    diffs: list[str] = []
    for relative_path in sorted(grouped):
        source_path = safe_source_path(root, relative_path)
        try:
            original_text = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RenderError(f"cannot read source file {relative_path}: {exc}") from exc
        except UnicodeDecodeError as exc:
            raise RenderError(f"source file is not valid UTF-8: {relative_path}") from exc

        original_lines = original_text.splitlines(keepends=True)
        changed_lines = list(original_lines)
        for operation in sorted(
            grouped[relative_path], key=lambda item: item["source"]["start_line"], reverse=True
        ):
            source = operation["source"]
            start = source["start_line"]
            end = source["end_line"]
            if start != end:
                raise RenderError(
                    f"{operation['id']}: automatic rendering supports one source line only"
                )
            if start > len(changed_lines):
                raise RenderError(
                    f"{operation['id']}: source line {start} exceeds {relative_path} length"
                )
            replacement_lines = render_list_item(operation, changed_lines[start - 1])
            changed_lines[start - 1 : end] = replacement_lines

        if changed_lines == original_lines:
            continue
        diffs.extend(
            difflib.unified_diff(
                original_lines,
                changed_lines,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
                lineterm="\n",
            )
        )

    return "".join(diffs)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        plan = load_plan(args.plan)
        selected = set(args.operation_ids) if args.operation_ids else None
        patch = render_patch(args.skill_directory, plan, selected)
    except (PlanValidationError, RenderError) as exc:
        diagnostics = exc.diagnostics if isinstance(exc, PlanValidationError) else [str(exc)]
        for diagnostic in diagnostics:
            print(f"render-patch: {diagnostic}", file=sys.stderr)
        return 1

    if args.output is None:
        sys.stdout.write(patch)
    else:
        try:
            args.output.write_text(patch, encoding="utf-8")
        except OSError as exc:
            print(f"render-patch: cannot write output: {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
